import functools
import hmac
import re

from flask import Flask, abort, jsonify, request
from loguru import logger

from proxyproof import __version__
from proxyproof.exceptions import PoolEmptyException
from proxyproof.probe.endpoint import all_keys
from proxyproof.setting import API_HOST, API_KEY, API_PORT, API_THREADED, IS_DEV, PROBE_MAX_AGE
from proxyproof.storages.pool import Pool

__all__ = ['app']

app = Flask(__name__)
if IS_DEV:
    app.debug = True

VALID_KEY_PATTERN = re.compile(r'^[a-zA-Z0-9_:\-]{1,64}$')

_pool = Pool()


def auth_required(func):
    @functools.wraps(func)
    def decorator(*args, **kwargs):
        if API_KEY == "":
            return func(*args, **kwargs)
        api_key = request.headers.get('API-KEY')
        if api_key is None:
            return {"message": "Please provide an API key in header"}, 400
        if request.method == "GET" and hmac.compare_digest(api_key, API_KEY):
            return func(*args, **kwargs)
        return {"message": "The provided API key is not valid"}, 403

    return decorator


def get_request_key():
    """读取 ?key=；不传则用第一个已配置的 key"""
    key = request.args.get('key')
    if key and not VALID_KEY_PATTERN.match(key):
        abort(400, description='invalid key parameter')
    if key and key not in all_keys() and _pool.count(key) == 0:
        abort(404, description='unknown key')
    return key or (all_keys() or ["default"])[0]


@app.errorhandler(PoolEmptyException)
def handle_empty(e):
    return jsonify({"message": "pool is empty", "hint": "retry later or switch key"}), 503


@app.route('/health')
@auth_required
def health():
    """健康检查：200=正常。给监控系统用（Uptime Kuma / UptimeRobot）。"""
    try:
        _pool.count(all_keys()[0] if all_keys() else "default")
        return "ok", 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)[:200]}), 503


@app.route('/')
@auth_required
def index():
    return f'<h2>Welcome to Proxy Pool System</h2><p>version {__version__}</p>'


@app.route('/random')
@auth_required
def get_proxy():
    """取代理：只从"max_age 秒内确认可用"的新鲜集合里 O(1) 随机。
    没有可用代理直接 503，绝不兜底发一个死代理。"""
    key = get_request_key()
    count = request.args.get('count', type=int) or 1
    max_age = request.args.get('max_age', type=int, default=PROBE_MAX_AGE)
    max_risk = request.args.get('max_risk', type=int)
    if count < 1:
        abort(400, description='count must be >= 1')

    proxies = _pool.pick(key, count=max(count, 3), max_age=max_age, max_risk=max_risk)
    if not proxies:
        raise PoolEmptyException
    proxies = proxies[:count]
    for p in proxies:
        _pool.serve_inc(key, p)
    if count == 1:
        return proxies[0]
    return '\n'.join(proxies)


@app.route('/all')
@auth_required
def get_proxy_all():
    key = get_request_key()
    max_age = request.args.get('max_age', type=int)
    return '\n'.join(_pool.all(key, max_age=max_age))


@app.route('/count')
@auth_required
def get_count():
    key = get_request_key()
    max_age = request.args.get('max_age', type=int)
    return str(_pool.count(key, max_age=max_age))


@app.route('/stats')
@auth_required
def get_stats():
    return jsonify({k: _pool.stats(k) for k in all_keys()})


@app.route('/report')
@auth_required
def report():
    """调用方反馈：真实请求成败。失败立即摘出新鲜集合，不等下一轮检测。"""
    proxy = request.args.get('proxy')
    ok = request.args.get('ok')
    if not proxy or ok not in ('0', '1'):
        abort(400, description='need proxy and ok=0|1')
    key = get_request_key()
    stat = _pool.report(key, proxy, ok == '1')
    return jsonify({"proxy": proxy, "ok": ok, "ewma": stat.get("ewma"),
                    "fail": stat.get("fail")})


if __name__ == '__main__':
    logger.info(f'starting api on {API_HOST}:{API_PORT}')
    app.run(host=API_HOST, port=API_PORT, threaded=API_THREADED)
