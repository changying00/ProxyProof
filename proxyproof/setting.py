import platform
import shutil
from os.path import abspath, dirname, join

from environs import Env
from loguru import logger

env = Env()
env.read_env()

# definition of flags
IS_WINDOWS = platform.system().lower() == 'windows'

# definition of dirs
ROOT_DIR = dirname(dirname(abspath(__file__)))
LOG_DIR = join(ROOT_DIR, env.str('LOG_DIR', 'logs'))

# definition of environments
DEV_MODE, TEST_MODE, PROD_MODE = 'dev', 'test', 'prod'
APP_ENV = env.str('APP_ENV', DEV_MODE).lower()
APP_DEBUG = env.bool('APP_DEBUG', True if APP_ENV == DEV_MODE else False)
APP_DEV = IS_DEV = APP_ENV == DEV_MODE
APP_PROD = IS_PROD = APP_ENV == PROD_MODE
APP_TEST = IS_TEST = APP_ENV == TEST_MODE


# Which WSGI container is used to run applications
# - gevent: pip install gevent
# - tornado: pip install tornado
# - meinheld: pip install meinheld
APP_PROD_METHOD_GEVENT = 'gevent'
APP_PROD_METHOD_TORNADO = 'tornado'
APP_PROD_METHOD_MEINHELD = 'meinheld'
APP_PROD_METHOD = env.str('APP_PROD_METHOD', APP_PROD_METHOD_GEVENT).lower()
APP_PROD_METHODS = (APP_PROD_METHOD_GEVENT, APP_PROD_METHOD_TORNADO, APP_PROD_METHOD_MEINHELD)
if APP_PROD_METHOD not in APP_PROD_METHODS:
    # 配错就在导入时炸，而不是等到 prod 的 server 子进程里才发现
    raise ValueError(f"APP_PROD_METHOD={APP_PROD_METHOD!r} 不支持，可选：{', '.join(APP_PROD_METHODS)}")

# redis host
REDIS_HOST = env.str('PROXYPROOF_REDIS_HOST',
                     env.str('REDIS_HOST', '127.0.0.1'))
# redis port
REDIS_PORT = env.int('PROXYPROOF_REDIS_PORT', env.int('REDIS_PORT', 6379))
# redis password, if no password, set it to None
REDIS_PASSWORD = env.str('PROXYPROOF_REDIS_PASSWORD',
                         env.str('REDIS_PASSWORD', None))
# redis db, if no choice, set it to 0
REDIS_DB = env.int('PROXYPROOF_REDIS_DB', env.int('REDIS_DB', 0))
# redis connection string, like redis://[password]@host:port or rediss://[password]@host:port/0,
# please refer to https://redis-py.readthedocs.io/en/stable/connections.html#redis.client.Redis.from_url
REDIS_CONNECTION_STRING = env.str(
    'PROXYPROOF_REDIS_CONNECTION_STRING', env.str('REDIS_CONNECTION_STRING', None))

# definition of proxy scores
# 新代理入池分数（不是满分，也不是 0）：满分 100 由评分公式算出
PROXY_SCORE_INIT = env.int('PROXY_SCORE_INIT', 10)
# 按来源加权：好源的代理初始分高、首检排得靠前（实测 AdvancedName 可用率 12%，
# 高产低质源 0.2%~1.4%）。没列出的源权重 1.0
SOURCE_WEIGHTS = env.json('SOURCE_WEIGHTS', {
    'AdvancedNameCrawler': 2.5,
    'ShiftyTRCrawler': 1.5,
    'KxDailiCrawler': 1.5,
    'IhuanCrawler': 1.5,
    'PrxchkCrawler': 1.5,
    'OpenProxyListCrawler': 0.5,
    'Proxy4ParsingCrawler': 0.5,
    'GeonodeCrawler': 0.5,
    'JetkaiCrawler': 0.5,
    'B4RC0DECrawler': 0.5,
})
# 僵尸代理清理：N 秒内没 OK 过的代理直接删除。免费代理生命周期分钟级，
# 不清理的话池子会被"偶尔活一次"的死代理占满
ZOMBIE_TTL = env.int('ZOMBIE_TTL', 7 * 24 * 3600)  # 7 天

# definition of proxy number
PROXY_NUMBER_MAX = env.int('PROXY_NUMBER_MAX', 3000)
# 只收国内 IP：开启后 getter 直接丢弃海外段代理，整个池子只服务国内站。
# 对淘宝/拼多多这类按 IP 段封机房地址的站，海外代理毫无价值还占探测配额
CN_ONLY = env.bool('CN_ONLY', False)

# definition of tester cycle, it will test every CYCLE_TESTER second
CYCLE_TESTER = env.int('CYCLE_TESTER', 20)
# definition of getter cycle, it will get proxy every CYCLE_GETTER second
CYCLE_GETTER = env.int('CYCLE_GETTER', 300)
GET_TIMEOUT = env.int('GET_TIMEOUT', 10)

# definition of tester

# ---------- 探测流水线（漏斗式）---------
# 身份探针：一次请求同时得到 存活 / 出口 IP / 延迟
PROBE_IDENTITY_URL = env.str('PROBE_IDENTITY_URL', 'http://ip.3322.net/')
# 身份探测的回退链：国内不同出口对个别站点的可达性差异很大，单一端点会制造 UNKNOWN
# 注意用 JSON（env.list 会按逗号切分，写 JSON 数组会解析成一堆带引号的碎片）
# 第一个换成 ip 直出的端点（3322 是公网测试池，偶发被墙；api.ipify.org 稳定且无地域差异）
PROBE_IDENTITY_URLS = env.json('PROBE_IDENTITY_URLS',
                               ['https://api.ipify.org?format=json', 'http://ip.3322.net/',
                                'http://myip.ipip.net/'])
# 本机出口 IP 会轮换（实测同一分钟出现过 182.118.238.2/.14/.39 和 IPv6），
# 所以基线是一组样本 + TTL，不是单个 IP
PROBE_BASELINE_TTL = env.int('PROBE_BASELINE_TTL', 600)
PROBE_TCP_TIMEOUT = env.float('PROBE_TCP_TIMEOUT', 0.8)
PROBE_TIMEOUT_IDENTITY = env.float('PROBE_TIMEOUT_IDENTITY', 3.0)
PROBE_TIMEOUT_TARGET = env.float('PROBE_TIMEOUT_TARGET', 6.0)
PROBE_CONCURRENCY = env.int('PROBE_CONCURRENCY', 100)
PROBE_BATCH = env.int('PROBE_BATCH', 200)
# 新入池代理的到期时间在 [0, N] 秒内打散，避免一次抓几万个把到期队列淹掉
INTRODUCE_WINDOW = env.int('INTRODUCE_WINDOW', 900)
# 分发新鲜度闸门：last_ok 超过这个秒数的代理不返回
PROBE_MAX_AGE = env.int('PROBE_MAX_AGE', 180)
# 每个 key = 一组目标；API 用 ?key= 选择。min_len 用于过滤挑战页/空壳页
# 默认目标是一个"用途就是被探测"的连通性端点：204、0 字节、为海量探测设计。
# 不要拿别人的内容站当探针，会把人家打限速。
PROBE_TARGETS = env.json('PROBE_TARGETS', {
    'default': [{'url': 'http://cp.cloudflare.com/', 'min_len': 0}],
})
# 可选的富化端点（仅新入池 + 24h 刷新，绝不每轮调用）
PROBE_ENRICH_URL = env.str('PROBE_ENRICH_URL', '')
PROBE_ENRICH_TTL = env.int('PROBE_ENRICH_TTL', 86400)

# definition of api
API_HOST = env.str('API_HOST', '0.0.0.0')
API_PORT = env.int('API_PORT', 5555)
API_THREADED = env.bool('API_THREADED', True)
# add an api key to get proxy
# need a header of `API-KEY` in get request to pass the authenticate
# API_KEY='', do not need `API-KEY` header
API_KEY = env.str('API_KEY', '')

# flags of enable
ENABLE_TESTER = env.bool('ENABLE_TESTER', True)
ENABLE_GETTER = env.bool('ENABLE_GETTER', True)
ENABLE_SERVER = env.bool('ENABLE_SERVER', True)


ENABLE_LOG_FILE = env.bool('ENABLE_LOG_FILE', True)
ENABLE_LOG_RUNTIME_FILE = env.bool('ENABLE_LOG_RUNTIME_FILE', True)
ENABLE_LOG_ERROR_FILE = env.bool('ENABLE_LOG_ERROR_FILE', True)


LOG_LEVEL_MAP = {
    DEV_MODE: "DEBUG",
    TEST_MODE: "INFO",
    PROD_MODE: "ERROR"
}

LOG_LEVEL = LOG_LEVEL_MAP.get(APP_ENV)
LOG_ROTATION = env.str('LOG_ROTATION', '500MB')
LOG_RETENTION = env.str('LOG_RETENTION', '1 week')

if ENABLE_LOG_FILE:
    if ENABLE_LOG_RUNTIME_FILE:
        logger.add(env.str('LOG_RUNTIME_FILE', join(LOG_DIR, 'runtime.log')),
                   level=LOG_LEVEL, rotation=LOG_ROTATION, retention=LOG_RETENTION)
    if ENABLE_LOG_ERROR_FILE:
        logger.add(env.str('LOG_ERROR_FILE', join(LOG_DIR, 'error.log')),
                   level='ERROR', rotation=LOG_ROTATION)
else:
    shutil.rmtree(LOG_DIR, ignore_errors=True)
