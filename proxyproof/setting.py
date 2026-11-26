import platform
from os.path import dirname, abspath, join
from environs import Env
from loguru import logger
import shutil


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

# definition of proxy number
PROXY_NUMBER_MAX = env.int('PROXY_NUMBER_MAX', 3000)

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
PROBE_IDENTITY_URLS = env.json('PROBE_IDENTITY_URLS',
                               ['http://ip.3322.net/', 'http://myip.ipip.net/'])
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
