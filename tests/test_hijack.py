"""劫持页判定的测试：200 但内容是壳/要求认证，不能算可用"""
from proxyproof.probe.verdict import is_target_ok, looks_hijacked


def test_normal_page_ok():
    body = '<!DOCTYPE html><html><body><h1>纵横中文网</h1>' + 'x' * 1000 + '</body></html>'
    assert not looks_hijacked(body)
    assert is_target_ok(200, body, 500)


def test_proxy_auth_required_is_not_ok():
    body = 'Proxy Authentication Required'
    assert looks_hijacked(body)
    assert not is_target_ok(200, body, 0)


def test_js_redirect_shell_is_not_ok():
    body = '<html><head><script>location.replace("http://ad.example.com/")</script></head></html>'
    assert looks_hijacked(body)
    assert not is_target_ok(200, body, 0)


def test_window_location_shell_is_not_ok():
    body = '<html><head><script>window.location="http://x.example"</script>'
    assert looks_hijacked(body)


def test_real_page_using_location_is_ok():
    """真实页面里带 location 跳转但以 doctype 开头，不该误杀"""
    body = '<!DOCTYPE html><html><head><script>location.href="/login";</script></head></html>'
    assert not looks_hijacked(body)
    assert is_target_ok(200, body, 0)


def test_empty_body_is_ok_for_204_endpoint():
    assert not looks_hijacked('')
    assert is_target_ok(204, '', 0)
