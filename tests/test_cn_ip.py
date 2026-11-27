"""CN_ONLY / cn key 的 IP 段过滤测试"""
import pytest

from proxyproof.utils.cn_ip import is_cn


@pytest.mark.parametrize("ip,expected", [
    ("110.39.156.195", True),    # 联通
    ("183.240.196.54", True),    # 移动
    ("120.136.23.170", True),    # 阿里云华南
    ("47.105.159.196", True),    # 阿里云青岛（47.104.0.0/13）
    ("8.8.8.8", False),          # 谷歌 DNS
    ("63.141.128.218", False),   # 美国
    ("103.21.244.124", False),   # 香港 Cloudflare
    ("not-an-ip", False),        # 解析失败
    ("", False),
])
def test_is_cn_common_segments(ip, expected):
    assert is_cn(ip) is expected

