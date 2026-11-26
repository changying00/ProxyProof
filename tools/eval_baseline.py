"""按 EVAL_STANDARD.md 计算评测指标。

用法: python eval.py [matrix3.jsonl] [retest.json]
"""
import json
import sys
from collections import Counter

MATRIX = sys.argv[1] if len(sys.argv) > 1 else "matrix3.jsonl"
RETEST = sys.argv[2] if len(sys.argv) > 2 else "retest.json"

THRESHOLDS = {
    "availability": 0.03,
    "precision": 0.90,
    "staleness_p90": 180,
    "false_kill": 0.05,
    "detect_latency": 300,
    "probe_cost": 1200,
}


def pct(a, b):
    return f"{a / b:.1%}" if b else "n/a"


def main():
    rows = [json.loads(l) for l in open(MATRIX, encoding="utf-8")]
    n = len(rows)
    plain = [r for r in rows if r["a_code"] == 200]
    conn = [r for r in rows if r["b_code"] == 200]
    target = [r for r in rows if r["c_code"]]
    both = [r for r in rows if r["a_code"] == 200 and r["b_code"] == 200]
    only_p = [r for r in rows if r["a_code"] == 200 and r["b_code"] != 200]
    only_c = [r for r in rows if r["a_code"] != 200 and r["b_code"] == 200]

    print(f"== 样本 {n} 个代理 ==")
    print(f"  明文可用            {len(plain):5d}  {pct(len(plain), n)}")
    print(f"  CONNECT 可用        {len(conn):5d}  {pct(len(conn), n)}")
    print(f"  目标站可达          {len(target):5d}  {pct(len(target), n)}")
    print(f"  能力交叉  双通 {len(both)} / 仅明文 {len(only_p)} / 仅CONNECT {len(only_c)}")
    avail = len(target) / n if n else 0
    print(f"\n  availability = {avail:.1%}   (目标 {THRESHOLDS['availability']:.0%}) "
          f"{'PASS' if avail >= THRESHOLDS['availability'] else 'FAIL'}")

    try:
        rt = json.load(open(RETEST))
    except FileNotFoundError:
        print("\n(缺少 retest.json，跳过可靠性指标)")
        return

    first_ok = [k for k, v in rt.items() if v[0] == 1]
    first_dead = [k for k, v in rt.items() if v[0] == 0]
    confirmed = [k for k in first_ok if sum(rt[k]) >= 2]
    false_pos = [k for k in first_ok if sum(rt[k]) < 2]
    revived = [k for k in first_dead if sum(rt[k]) >= 2]
    flip = [k for k in first_ok if any(x != 1 for x in rt[k])]

    precision = len(confirmed) / len(first_ok) if first_ok else 0
    recall = len(confirmed) / (len(confirmed) + len(revived)) if (confirmed or revived) else 0

    print(f"\n== 单次探测可靠性（3 轮复测，间隔 20s）==")
    print(f"  首测判活 {len(first_ok)}  其中复测确认 {len(confirmed)}  假阳性 {len(false_pos)}")
    print(f"  首测判死 {len(first_dead)}  其中复测复活 {len(revived)}  漏报率 {pct(len(revived), len(first_dead))}")
    print(f"  precision = {precision:.1%}  (目标 {THRESHOLDS['precision']:.0%}) "
          f"{'PASS' if precision >= THRESHOLDS['precision'] else 'FAIL'}")
    print(f"  recall    = {recall:.1%}    (无独立阈值，作为参考)")
    print(f"  翻转率    = {pct(len(flip), len(first_ok))}  → "
          f"{'单次探测不够，需 ≥2 次确认' if len(flip) / len(first_ok) > 0.05 else '单次探测可信'}")

    print("\n== 待补的指标（需要 /report 反馈与 last_ok 时间戳）==")
    for k in ("staleness_p90", "false_kill", "detect_latency"):
        print(f"  {k:16s} 未采集（阈值 {THRESHOLDS[k]}）")
    print(f"  probe_cost       当前每千代理约 3000 请求（阈值 {THRESHOLDS['probe_cost']}，FAIL）")


if __name__ == "__main__":
    main()
