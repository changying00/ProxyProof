"""匿名性三级判定：透明 / 匿名 / 高匿。

判定方法：经代理请求一个"回显请求头"的端点，检查目标站看到的请求头。

  transparent  代理把你的 IP 透传（X-Forwarded-For 含你的 IP）
  anonymous    代理藏了你的 IP 但暴露了代理身份（有 Via / X-Forwarded-For 等）
  elite        代理完全隐藏：不透传你的 IP，也不暴露代理身份

探测端点需返回 JSON 格式的请求头（如 httpbin.org/headers），
本模块解析后返回匿名等级。
"""
import json
import re

# 常见的代理暴露头
PROXY_HEADERS = (
    "via",
    "x-forwarded-for",
    "x-forwarded",
    "proxy-connection",
    "proxy-agent",
    "x-proxy",
    "forwarded",
    "client-ip",
    "x-real-ip",
)

# 解析 IP 地址
IPV4 = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')


def classify_anonymity(headers: dict, real_ip: str) -> str:
    """根据目标站收到的请求头判断匿名等级。

    headers: 代理转发后目标站看到的请求头
    real_ip: 你的本机出口 IP

    返回: "transparent" / "anonymous" / "elite"
    """
    # 全部转小写方便比较
    lower = {k.lower(): v for k, v in headers.items()}
    all_values = " ".join(str(v).lower() for v in lower.values())

    # 1. 检查你的真实 IP 是否泄露
    if real_ip and real_ip.lower() in all_values:
        return "transparent"

    # 2. 检查是否有代理暴露头
    proxy_headers_found = any(h in lower for h in PROXY_HEADERS)
    if proxy_headers_found:
        # 确认暴露头里不含你的 IP
        for h in PROXY_HEADERS:
            val = lower.get(h, "")
            if real_ip and real_ip.lower() in str(val).lower():
                return "transparent"
        return "anonymous"

    return "elite"


def parse_headers_response(body: str) -> dict:
    """解析 httpbin.org/headers 的 JSON 响应，返回请求头 dict。

    兼容格式：{"headers": {"Via": "...", ...}} 或直接 {...}
    """
    try:
        data = json.loads(body)
        if isinstance(data, dict):
            if "headers" in data and isinstance(data["headers"], dict):
                return data["headers"]
            return data
    except (json.JSONDecodeError, ValueError):
        pass
    return {}
