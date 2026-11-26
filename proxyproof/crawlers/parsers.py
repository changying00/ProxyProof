"""
共享解析工具：给新扩展的免费代理源复用。

只做“文本 -> (host, port)”的抽取与合法性校验，不碰网络、不碰存储，
这样每个爬虫文件可以保持很短，和项目原有 public/*.py 的写法一致。
"""
import re

# 严格行格式：1.2.3.4:8080
# 允许 scheme 前缀、认证信息、以及任意分隔的尾部字段
# （如 hideip.me 的 `ip:port:国家`、spys.me 的 `ip:port US-H-S -`）
LINE_PATTERN = re.compile(
    r'^(?:(?:https?|socks[45]?)://)?'
    r'(?:[^\s:@/]+(?::[^\s@/]*)?@)?'
    r'(\d{1,3}(?:\.\d{1,3}){3}):(\d{1,5})'
    r'(?:[:#\s].*)?$'
)

# 宽松格式：从混排文本里捞 IP:端口（用于 HTML 表格、带国家后缀的列表）
LOOSE_PATTERN = re.compile(r'(\d{1,3}(?:\.\d{1,3}){3})\D{0,12}?(\d{1,5})')


def is_ipv4(host):
    parts = host.split('.')
    if len(parts) != 4:
        return False
    for part in parts:
        if not part.isdigit():
            return False
        if not 0 <= int(part) <= 255:
            return False
    return True


def is_port(port):
    return 1 <= port <= 65535


def normalize_proxy(host, port):
    """
    校验并归一化，(host, port) 不合法时返回 None
    """
    host = (host or '').strip()
    if not is_ipv4(host):
        return None
    try:
        port = int(str(port).strip())
    except (TypeError, ValueError):
        return None
    if not is_port(port):
        return None
    return host, port


def iter_line_proxies(text):
    """
    逐行解析纯文本代理列表（每行一个 ip:port）
    """
    for line in (text or '').splitlines():
        line = line.strip()
        if not line:
            continue
        match = LINE_PATTERN.match(line)
        if not match:
            continue
        proxy = normalize_proxy(match.group(1), match.group(2))
        if proxy:
            yield proxy


def iter_text_proxies(text):
    """
    从任意混合文本里抽取 ip:port，用于格式不太规整的源
    """
    for host, port in LOOSE_PATTERN.findall(text or ''):
        proxy = normalize_proxy(host, port)
        if proxy:
            yield proxy
