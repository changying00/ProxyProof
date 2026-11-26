# 怎么运行

## 0. 前置

| 项 | 状态 | 说明 |
|---|---|---|
| Python | `.venv/Scripts/python.exe` | 依赖已装（redis/aiohttp/flask/loguru…） |
| Redis | 127.0.0.1:6379 | 已在本机运行，池数据在 **db0** |
| 配置 | `.env` | 从 `.env.example` 复制：`cp .env.example .env`，改目标站/阈值改这里 |

## 1. 一条命令启动

在 **`Desktop/Proxy_Pool/ProxyProof`** 目录下：

```bash
.venv/Scripts/python.exe run.py
```

会起三个进程：`tester`（检测）/ `getter`（抓取）/ `server`（API）。

也可以只跑其中一个：

```bash
.venv/Scripts/python.exe run.py --processor tester
.venv/Scripts/python.exe run.py --processor getter
.venv/Scripts/python.exe run.py --processor server
```

## 2. 验证它真的在工作

```bash
curl http://127.0.0.1:5555/stats     # 池子状态
curl http://127.0.0.1:5555/count     # 池内总数
curl http://127.0.0.1:5555/random    # 取一个可用代理
curl "http://127.0.0.1:5555/random?count=5"   # 取 5 个（换行分隔）
```

`/stats` 各字段：

```
total     池内代理总数
fresh     新鲜可用数（max_age 秒内确认过的，只有这些会被发出去）
due       到期待检测数
verdicts  最近一次判定分布：OK / BLOCKED / DEAD / UNKNOWN
```

**刚启动是空的**：getter 要先爬一轮，tester 再逐个探测，`fresh` 才会从 0 涨上来。
实测约 2~4 分钟到 20~40 个可用。

用返回的代理做一次真实请求：

```bash
P=$(curl -s http://127.0.0.1:5555/random)
curl -x "http://$P" -m 10 -o /dev/null -w '%{http_code} %{size_download}B\n' http://你的目标/
```

## 3. 停止

```bash
.venv/Scripts/python.exe tools/stop.py
```

> 不要用 `Ctrl+C` 或任务管理器。调度器 spawn 的子进程命令行里没有项目路径，
> 手动杀很容易留下孤儿进程继续抓取/探测，还会占着 5555 端口。

## 4. 配置（`.env`）

```ini
# 目标站：每个 key 一组，API 用 ?key= 选择
PROBE_TARGETS={"default":[{"url":"http://www.163.com/","min_len":5000}]}

PROBE_MAX_AGE=120          # 分发新鲜度闸门（秒）——大于这个年龄的不发
CYCLE_TESTER=20            # 检测器每轮的时间预算（秒）
CYCLE_GETTER=300           # 抓取周期（秒）
PROXY_NUMBER_MAX=3000      # 池子上限，防止一次灌爆
INTRODUCE_WINDOW=900       # 新代理的首次检测在 0~900s 内打散
PROBE_CONCURRENCY=100      # 探测并发
API_PORT=5555
API_KEY=                   # 留空=不鉴权；填了就要带 API-KEY 头
```

**加一个新目标站**（比如你的真实站点），配两行：

```ini
PROBE_TARGETS={"default":[{"url":"http://www.163.com/","min_len":5000}],"mysite":[{"url":"https://www.example.com/","min_len":5000}]}
```

然后 `curl "http://127.0.0.1:5555/random?key=mysite"`。两个 key 的分数完全独立。

## 5. 接进自己的爬虫

```python
import requests

def get_proxy(key="default"):
    r = requests.get(f"http://127.0.0.1:5555/random?key={key}", timeout=5)
    if r.status_code == 503:          # 池子暂时没有可用代理
        return None
    return r.text.strip()

proxy = get_proxy()
try:
    resp = requests.get(url, proxies={"http": f"http://{proxy}", "https": f"http://{proxy}"}, timeout=10)
    if resp.status_code >= 400:
        raise ValueError(resp.status_code)
except Exception:
    # 真实失败立刻反馈，池子会把它摘掉，不用等下一轮检测
    requests.get(f"http://127.0.0.1:5555/report?proxy={proxy}&ok=0", timeout=3)
```

`/report` 是关键：一次真实失败比十次探测更有信息量。

## 6. 常见问题

| 现象 | 原因 / 处理 |
|---|---|
| `/random` 一直返回 503 | 池子在预热，看 `/stats` 的 `total` 是否在涨；或 `fresh=0`（全都过期了，看 tester 是否在跑） |
| `fresh` 一直是 0 | 目标站不通。换成你能打开的站，或调大 `PROBE_TIMEOUT_TARGET` |
| 端口 5555 被占用 | 上次没退干净：`python tools/stop.py` 后重试 |
| 想清空重来 | `redis-cli -n 0 --scan --pattern 'pool:*' \| xargs redis-cli -n 0 del`，或停掉后删 `pool:*` |
| 日志 | `logs/runtime.log`（INFO）、`logs/error.log`（ERROR） |
