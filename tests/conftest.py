"""pytest 的全局准备。

原则：测试只碰一个独立的 Redis 库（默认 db 5）和一个独立的键前缀，
绝不碰正在运行的池（db0 里的 pool:*）。换库用 TEST_REDIS_DB=6。
"""

import os
import tempfile

# setting.py 在导入时就读环境变量，所以这些必须在任何 `import proxyproof.*` 之前设好
os.environ["REDIS_DB"] = os.environ.get("TEST_REDIS_DB", "5")
os.environ["REDIS_CONNECTION_STRING"] = ""  # 连接串会绕过 REDIS_DB，必须清掉
os.environ["API_KEY"] = ""  # 接口不需要请求头
os.environ["LOG_DIR"] = tempfile.mkdtemp(prefix="proxyproof-test-")  # 日志别写进项目的 logs/
for _name in list(os.environ):
    if _name.startswith("PROXYPROOF_REDIS_"):
        del os.environ[_name]
