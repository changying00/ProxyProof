"""匿名性三级判定的测试"""
from proxyproof.probe.anonymity import classify_anonymity, parse_headers_response

REAL_IP = "192.168.1.1"


def test_elite_no_proxy_headers():
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "*/*"}
    assert classify_anonymity(headers, REAL_IP) == "elite"


def test_transparent_leaks_real_ip():
    headers = {"X-Forwarded-For": f"{REAL_IP}, 10.0.0.1"}
    assert classify_anonymity(headers, REAL_IP) == "transparent"


def test_transparent_real_ip_in_any_header():
    headers = {"Via": "1.1 proxy", "X-Real-IP": REAL_IP}
    assert classify_anonymity(headers, REAL_IP) == "transparent"


def test_anonymous_exposes_proxy_identity():
    headers = {"Via": "1.1 some-proxy", "X-Forwarded-For": "10.0.0.1"}
    assert classify_anonymity(headers, REAL_IP) == "anonymous"


def test_anonymous_x_forwarded_for_without_real_ip():
    headers = {"X-Forwarded-For": "10.0.0.1, 172.16.0.1"}
    assert classify_anonymity(headers, REAL_IP) == "anonymous"


def test_no_real_ip_still_elite():
    headers = {"User-Agent": "Mozilla/5.0"}
    assert classify_anonymity(headers, "") == "elite"


def test_parse_headers_json_wrapped():
    body = '{"headers": {"Via": "proxy", "User-Agent": "test"}}'
    result = parse_headers_response(body)
    assert result == {"Via": "proxy", "User-Agent": "test"}


def test_parse_headers_json_flat():
    body = '{"Via": "proxy"}'
    result = parse_headers_response(body)
    assert result == {"Via": "proxy"}


def test_parse_headers_invalid_json():
    assert parse_headers_response("not json") == {}
    assert parse_headers_response("") == {}
