"""离线评测脚本：对手工抽样得到的探测结果算几个指标。

开发期用来比较「改动前 / 改动后」，跑代理池本身用不到它。
输入文件不入库，需要自己准备：

    python tools/eval_baseline.py matrix3.jsonl retest.json

matrix3.jsonl  每行一个代理的 JSON，至少含三个状态码：
               a_code = 经代理明文 GET 的状态码
               b_code = 经代理 CONNECT 的状态码
               c_code = 经代理请求目标站的状态码（非 0 即视为可达）
retest.json    {"ip:port": [1, 0, 1], ...}，同一批代理间隔 20s 复测 3 轮的结果

输出的指标：
    availability  目标站可达的代理数 / 样本总数
    precision      首测判活、且 3 轮复测里 >= 2 轮仍活的比例
    recall         复测确认仍活的 / (确认仍活 + 首测判死但复测复活)
    翻转率         首测判活的代理里，复测出现过失败的比例

THRESHOLDS 是开发期定的验收线，只用来标 PASS / FAIL。
"""

import json
import sys

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
    with open(MATRIX, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f]
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
        with open(RETEST, encoding="utf-8") as f:
            rt = json.load(f)
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

    print("\n== 单次探测可靠性（3 轮复测，间隔 20s）==")
    print(f"  首测判活 {len(first_ok)}  其中复测确认 {len(confirmed)}  假阳性 {len(false_pos)}")
    print(f"  首测判死 {len(first_dead)}  其中复测复活 {len(revived)}  漏报率 {pct(len(revived), len(first_dead))}")
    print(f"  precision = {precision:.1%}  (目标 {THRESHOLDS['precision']:.0%}) "
          f"{'PASS' if precision >= THRESHOLDS['precision'] else 'FAIL'}")
    print(f"  recall    = {recall:.1%}    (无独立阈值，作为参考)")
    flip_rate = len(flip) / len(first_ok) if first_ok else 0
    print(f"  翻转率    = {pct(len(flip), len(first_ok))}  → "
          f"{'单次探测不够，需 ≥2 次确认' if flip_rate > 0.05 else '单次探测可信'}")

    print("\n== 这个脚本没算的指标（阈值见 THRESHOLDS）==")
    for k in ("staleness_p90", "false_kill", "detect_latency", "probe_cost"):
        print(f"  {k:16s} 未采集（阈值 {THRESHOLDS[k]}）")


if __name__ == "__main__":
    main()
