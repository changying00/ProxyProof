"""四态判定 —— 代理池检测的唯一合法输出。

    OK       目标返回可接受响应
    BLOCKED  代理层活着（身份探针通过），但目标拒绝/超时/挑战页
    DEAD     TCP 层面就不通
    UNKNOWN  探针自身异常（超时/5xx/坏JSON），分数不动

判定顺序不可颠倒：BLOCKED 必须以"身份探针通过"为前提，否则只能是 UNKNOWN。
"""

OK = "OK"
BLOCKED = "BLOCKED"
DEAD = "DEAD"
UNKNOWN = "UNKNOWN"

VERDICTS = (OK, BLOCKED, DEAD, UNKNOWN)

# 分数只在这两种判定下变化
SCORING_VERDICTS = (OK, BLOCKED)

# 挑战页 / 拦截页特征，命中即视为目标不可用
CHALLENGE_MARKERS = (
    "just a moment",
    "cf-challenge",
    "cf_chl_opt",
    "attention required",
    "verify you are human",
    "captcha",
    "access denied",
    "访问验证",
    "安全检查",
    "人机验证",
    "请开启javascript",
    "请启用javascript",
    "forbidden",
)

# 站点白名单状态码：3xx 也算通（很多站点首跳是重定向）
VALID_STATUS = (200, 203, 204, 206, 301, 302, 303, 307, 308)


def looks_challenged(status, body):
    """响应体命中挑战特征 → 目标其实没给内容"""
    if not body:
        return False
    head = body[:4000].lower()
    return any(m in head for m in CHALLENGE_MARKERS)


def is_target_ok(status, body, min_len=0):
    """目标响应是否算通过"""
    if status not in VALID_STATUS:
        return False
    if min_len and len(body or "") < min_len:
        return False
    if looks_challenged(status, body):
        return False
    return True


def next_check_delay(verdict, streak=0):
    """到期队列的退避秒数（免费代理 TTL 是分钟级，不要做成小时级）

    注意：OK 的复检间隔必须明显小于分发的新鲜度闸门（PROBE_MAX_AGE），
    否则代理会在"刚过期"和"下次复检"之间留出一段空窗，池子永远发不出东西。
    """
    if verdict == OK:
        # 免费代理 TTL 秒级：复检越快，fresh 里「已经死了但还没被发现」的越少。
        # 实测 45s 复检下 fresh 仍有 ~60% 拿出去即死；30s 是吞吐和时效的平衡点
        return 30
    if verdict == BLOCKED:
        return 600
    if verdict == DEAD:
        return 300 if streak <= 1 else 900
    return 60  # UNKNOWN 快速重试，且不扣分


def should_drop(verdict, streak):
    """连续 DEAD 才允许删除；BLOCKED / UNKNOWN 永远不删"""
    return verdict == DEAD and streak >= 3
