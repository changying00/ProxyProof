# ProxyProof

[![CI](https://github.com/changying00/ProxyProof/actions/workflows/ci.yml/badge.svg)](https://github.com/changying00/ProxyProof/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)
![](https://img.shields.io/badge/python-3.9%2B-brightgreen)
![](https://img.shields.io/badge/redis-5.0%2B-red)

[English](./README.en.md)

Python 代理池：抓取免费代理，按目标站点验证可用性，通过 HTTP API 取用。

```console
$ curl localhost:5555/random            # 取一个刚确认过能用的代理
39.109.113.97:4090

$ curl localhost:5555/stats             # 池子现状
{"default": {"total": 2899, "fresh": 149, "due": 841,
             "verdicts": {"OK": 167, "BLOCKED": 73, "DEAD": 2094, "UNKNOWN": 172}}}
```

`fresh` 是「最近 `PROBE_MAX_AGE` 秒内确认可用」的数量，`/random` 只从这里取。一个都没有时返回 `503`，不会拿没验证过的代理凑数。

- 33 个免费代理源定时抓取，Redis 存储，HTTP API 取用（`/random` `/all` `/count` `/stats` `/report`）
- 按目标站点分别记分，判定分四态，只发最近确认过能用的代理
- 探测走漏斗（TCP → 身份 → 目标），死代理 0.8 秒出局；默认探针是 Cloudflare 的连通性端点，不给任何站点添负担

## 谁适合用

- **适合**：想弄明白代理池是怎么设计的、有小规模抓取任务、不想买付费代理。
- **不适合**：生产级的大规模采集。免费代理的可用率只有百分之几（本机实测：3000 个代理里，能用的在几十到三百之间波动），这个量级直接买付费代理更省事。

## 快速开始

### Docker 一键部署（推荐，Ubuntu/Debian）

一条命令搞定（装 Docker → 拉代码 → 配置 → 启动）：

```bash
curl -fsSL https://raw.githubusercontent.com/changying00/ProxyProof/master/deploy.sh | bash
```

完成后自动输出 API 地址和监控地址。换端口：`bash deploy.sh 18473`。

### Docker 手动部署

需要 Docker 和 compose v2。更详细的部署说明见 [DOCKER.md](./DOCKER.md)。

```bash
git clone https://github.com/changying00/ProxyProof.git
cd ProxyProof
cp .env.example .env      # 按需改探测目标和端口
docker compose pull       # 用预构建镜像（快）
docker compose up -d
curl http://127.0.0.1:5555/random
```

Redis 随 compose 一起起，数据落在 named volume 里，容器重启后池子不清零。

### 直接跑（Python）

需要 Python >= 3.9、Redis 5.0 及以上（不依赖 6.2 才有的 `ZRANDMEMBER`）。

```bash
git clone https://github.com/changying00/ProxyProof.git
cd ProxyProof
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # Redis 不在本机时改 REDIS_HOST / REDIS_PASSWORD
python3 run.py
```

刚启动时池子是空的：getter 先爬一轮（约 1 分钟），tester 再逐个探测，`fresh` 要 2~4 分钟才涨上来。之后：

```bash
curl http://127.0.0.1:5555/random
```

也可以按需分别运行：

```bash
python3 run.py --processor getter
python3 run.py --processor tester
python3 run.py --processor server
```

运行后日志类似：

```
2026-11-26 20:19:43 | INFO | proxyproof.scheduler:run:100 - starting proxyproof...
2026-11-26 20:19:43 | INFO | proxyproof.scheduler:run:104 - starting tester...
2026-11-26 20:19:43 | INFO | proxyproof.scheduler:run:110 - starting getter...
2026-11-26 20:19:43 | INFO | proxyproof.scheduler:run:116 - starting server...
2026-11-26 20:19:50 | INFO | proxyproof.processors.tester:_pass:40 - [default] probed 200 fresh=12 total=3000
```

**停止**用 `python3 tools/stop.py`。不要用 Ctrl+C 或任务管理器——调度器 spawn 出的子进程命令行里没有项目路径，手动 kill 容易留下孤儿进程继续抓取，还占着端口。

`.env` 列了全部可配置项并逐行写了注释，通常只有 `REDIS_HOST` / `REDIS_PASSWORD` 需要改。`.env` 已在 `.gitignore` 里，写密码不会被提交。

## 和常见代理池的区别

大多数代理池的判定是「这个代理能不能连上百度」，对你真正要访问的站点几乎没有预测力——连得上百度，不代表能打开你的目标站。

本项目按 `(代理 × 目标 × 时刻)` 记分：

- 每个 `key` 对应一组目标 URL，代理对每个 key 单独记分，互不影响。用法见[按目标分组取代理](#按目标分组取代理)。
- 判定分四态：`OK` / `BLOCKED`（代理活着但目标不通）/ `DEAD`（连不上）/ `UNKNOWN`（探针自己出问题）。`BLOCKED` 降权不删除，`UNKNOWN` 不扣分——第三方探针抖一下，不会把好代理误杀。
- 只有「最近 `PROBE_MAX_AGE` 秒内确认可用」的代理才会被发出，否则返回 `503`。

探测目标该怎么选、为什么默认是 `cp.cloudflare.com`，见[探测目标怎么选](#探测目标怎么选)。

## 匿名性筛选

免费代理大部分是**透明代理**——你的真实 IP 会泄露给目标站，爬东西等于裸奔。本项目在探测时自动检测匿名等级，分三级：

| 等级 | 含义 | 评分系数 | 默认行为 |
|---|---|---|---|
| `elite`（高匿） | 不透传你的 IP，也不暴露代理身份 | ×1.0 | 正常分发 |
| `anonymous`（匿名） | 藏了你的 IP，但暴露了代理身份 | ×0.9 | 正常分发 |
| `transparent`（透明） | 你的真实 IP 直接泄露给目标站 | ×0.0 | 不分发 |
| `unknown` | 未能检测 | ×0.85 | 正常分发 |

检测方法：经代理请求 `http://httpbin.org/headers`，检查目标站收到的请求头里有没有你的 IP（透明）、有没有 `Via`/`X-Forwarded-For` 等代理头（匿名）。

想只发高匿代理（推荐爬淘宝/安居客时用）：

```ini
ANON_MIN_LEVEL=elite
```

设置后只有 `elite` 代理会进 `fresh` 池。注意免费代理里高匿的极少（实测不到 5%），开了这个选项池子会小很多。

检测端点可换成自建的（免费且不限量）：

```ini
PROBE_ANON_CHECK_URL=http://你的服务器/headers
```

## 使用

```bash
curl http://127.0.0.1:5555/random
```

程序对接示例：

```python
import requests

proxyproof_url = 'http://127.0.0.1:5555/random'
target_url = 'http://你的目标/'

def get_random_proxy():
    r = requests.get(proxyproof_url, timeout=5)
    if r.status_code == 503:        # 池子暂时没有可用代理
        return None
    return r.text.strip()

def crawl(url, proxy):
    proxies = {'http': 'http://' + proxy}
    return requests.get(url, proxies=proxies, timeout=10).text


def main():
    proxy = get_random_proxy()
    if not proxy:
        return
    print('get random proxy', proxy)
    print(crawl(target_url, proxy)[:200])

if __name__ == '__main__':
    main()
```

完整示例见 [examples/usage.py](./examples/usage.py)。

### 获取多个代理

```
GET http://localhost:5555/random?count=5
```

`count` 不传或为 1 时返回单个；大于可用数量时返回全部。可与 `key` 组合。

### 按目标分组取代理

先在 `PROBE_TARGETS` 里加一个 `key`（写法见[探测目标怎么选](#探测目标怎么选)），然后：

```
GET http://localhost:5555/random?key=mysite
GET http://localhost:5555/count?key=mysite
```

两个池子的分数完全独立：一个代理在 `default` 里可能 95 分，在你的站上 0 分。

### 国内站专用池（CN_ONLY）

爬淘宝/拼多多这类按 IP 段封机房地址的站，海外代理毫无价值。设 `CN_ONLY=true` 后 getter 在**源头**丢弃海外段 IP，整个池子只收国内段：

```ini
CN_ONLY=true
PROBE_TARGETS={"default":[{"url":"https://www.baidu.com/","min_len":500}]}
```

然后 `GET /random?key=default` 拿到的就都是国内段、且经国内站点验证过的代理。

### 上报使用结果

调用方的一次真实失败，比探测器十次探测更有信息量：

```
GET http://localhost:5555/report?proxy=1.2.3.4:80&ok=0
```

失败会立即把该代理摘出新鲜集合，不用等下一轮检测；成功则刷新其新鲜度。

### 池子状态

```
GET http://localhost:5555/stats
```

返回每个 key 的 `total`（池内总数）、`fresh`（新鲜可用）、`due`（待检测）、`verdicts`（最近判定分布）。

### 健康检查

```
GET http://localhost:5555/health
```

返回 `200 ok`（正常）或 `503`（Redis 不可达）。给 Uptime Kuma / UptimeRobot 等监控系统用。

## 可配置项

所有配置通过环境变量设置，可以写进项目根目录的 `.env`（`environs` 会自动读取）。完整清单见 [.env.example](./.env.example)。

### 开关

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `ENABLE_GETTER` | `true` | 是否启用获取器 |
| `ENABLE_TESTER` | `true` | 是否启用检测器 |
| `ENABLE_SERVER` | `true` | 是否启用 API 服务 |

### 环境

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `APP_ENV` | `dev` | `dev`（DEBUG 日志）/ `test`（INFO 日志，推荐日常用）/ `prod`（ERROR） |
| `APP_DEBUG` | `dev` 下为 `true` | Flask 调试模式 |
| `APP_PROD_METHOD` | `gevent` | `prod` 下的 WSGI 容器：`gevent` / `tornado` / `meinheld`（后两者需自行安装） |

### Redis 连接

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `REDIS_HOST` | `127.0.0.1` | Redis 地址 |
| `REDIS_PORT` | `6379` | Redis 端口 |
| `REDIS_PASSWORD` | 空 | Redis 密码 |
| `REDIS_DB` | `0` | Redis 库号 |
| `REDIS_CONNECTION_STRING` | 空 | 连接串，设置后优先于上面四项 |

### 目标与探测

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `PROBE_TARGETS` | `{"default":[{"url":"https://cp.cloudflare.com/","min_len":0}]}` | 目标分组，JSON |
| `PROBE_IDENTITY_URLS` | `["http://ip.3322.net/","http://myip.ipip.net/"]` | 身份探针回退链，返回出口 IP |
| `PROBE_TCP_TIMEOUT` | `0.8` | TCP 探测超时（秒） |
| `PROBE_TIMEOUT_IDENTITY` | `3` | 身份探测超时 |
| `PROBE_TIMEOUT_TARGET` | `6` | 目标探测超时 |
| `PROBE_CONCURRENCY` | `100` | 探测并发数 |
| `PROBE_BATCH` | `200` | 单批探测数量 |
| `PROBE_ANON_CHECK_URL` | `http://httpbin.org/headers` | 匿名性检测端点（回显请求头的 JSON） |
| `ANON_MIN_LEVEL` | 空 | 分发匿名门槛：空=不限 / `anonymous` / `elite` |

`min_len` 是响应体长度下限，用来排掉挑战页和空壳页。204 端点设为 0。

### 池容量与调度

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `PROXY_NUMBER_MAX` | `3000` | 池子上限 |
| `PROXY_SCORE_INIT` | `10` | 新代理入池初始分 |
| `SOURCE_WEIGHTS` | 见下 | 按来源加权（好源初始分高、首检排前面） |
| `CN_ONLY` | `false` | `true` 时只收国内段 IP（源头过滤） |
| `ZOMBIE_TTL` | `604800` | 僵尸清理：N 秒内没 OK 过就删（默认 7 天） |
| `PROBE_ENRICH_URL` | 空 | IP 质量富化 API（如 `http://ip-api.com/json/{ip}`），留空不富化 |
| `PROBE_ENRICH_TTL` | `86400` | 富化结果刷新周期（秒） |
| `INTRODUCE_WINDOW` | `900` | 新代理首次检测打散窗口（秒） |
| `CYCLE_TESTER` | `20` | 检测器每轮的时间预算（秒） |
| `CYCLE_GETTER` | `300` | 抓取周期（秒） |
| `PROBE_MAX_AGE` | `120` | 分发新鲜度闸门（秒），建议 ≥ OK 复检间隔（30s） |
| `GET_TIMEOUT` | `10` | 爬虫请求超时 |

`SOURCE_WEIGHTS` 默认值（JSON，可覆盖）：好源 `AdvancedNameCrawler: 2.5`、`ShiftyTR/KxDaili/Ihuan/Prxchk: 1.5`，高产低质源 `Geonode/Jetkai/B4RC0DE/OpenProxyList/Proxy4Parsing: 0.5`。权重越大，初始分越高、首检排得越靠前。

> 上限不是越大越好。`fresh` 的天花板 ≈ 检测吞吐 × 可用率 × 新鲜窗口，和池子大小无关：上限调大之后，每个代理被复检的间隔会跟着变长，多出来的代理只会摊薄检测频率。

### API 与日志

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `API_HOST` | `0.0.0.0` | 只给本机用可改 `127.0.0.1` |
| `API_PORT` | `5555` | API 端口 |
| `API_THREADED` | `true` | Flask 多线程 |
| `API_KEY` | 空 | 设置后请求需带 `API-KEY` 头 |
| `ENABLE_LOG_FILE` | `true` | 是否写日志文件 |
| `LOG_ROTATION` | `500MB` | 日志轮转大小 |
| `LOG_RETENTION` | `1 week` | 日志保留时长 |

## 探测目标怎么选

**这是整套系统里最需要想清楚的一件事**：探测器会对目标发请求，池子越大，请求越多。

默认用的是 `https://cp.cloudflare.com/`——Cloudflare 专门为「连通性检测」提供的端点，返回 204、0 字节，面向海量探测设计。拿它当探针，等于不占用任何人的带宽，也不会把谁打限速。

**不要拿别人的内容站当探针。** 我实测过：拿某资讯站（首页 271KB）当目标，跑几万个代理之后，对方直接把我本机 IP 限速到 11 秒响应。这不是「测试」，这是小型 CC。

所以推荐的分工是：

| key | 目标 | 用途 |
|---|---|---|
| `default` | `https://cp.cloudflare.com/` | 通用池：验证代理能对 HTTPS 建 CONNECT 隧道（这才是爬 https 站的前提） |
| 你的站 | 你自己的目标页 | 专用池：额外验证「代理能打开这个站」 |

```ini
PROBE_TARGETS={"default":[{"url":"https://cp.cloudflare.com/","min_len":0}],"mysite":[{"url":"https://你的站/","min_len":3000}]}
```

然后 `GET /random?key=mysite`。两个池子的分数完全独立：一个代理在 `default` 里可能 95 分，在你的站上 0 分。

如果你有服务器，最稳的做法是自己起一个端点（返回 204 或一句固定文本），把它写进 `PROBE_TARGETS`——完全不依赖第三方。

## 扩展代理爬虫

在 `proxyproof/crawlers/public/` 下新建文件，继承 `BaseCrawler` 即可自动加载：

```python
from pyquery import PyQuery as pq

from proxyproof.crawlers.base import BaseCrawler
from proxyproof.schemas.proxy import Proxy

BASE_URL = 'http://example.com/{page}'
MAX_PAGE = 5


class ExampleCrawler(BaseCrawler):
    """
    example.com, http://example.com
    """
    urls = [BASE_URL.format(page=page) for page in range(1, MAX_PAGE + 1)]

    def parse(self, html):
        doc = pq(html)
        for item in doc('table tr').items():
            ip = item.find('.ip').text()
            port = item.find('.port').text()
            if ip and port:
                yield Proxy(host=ip, port=int(port))
```

如果源是"每行一个 `ip:port`"的纯文本列表，继承 `proxyproof/crawlers/base_list.py` 的 `TextListCrawler`，只声明 `urls` 就行。

爬虫的 HTTP 请求强制不走系统代理（`trust_env=False`），这样本机开不开 Clash 都不影响抓取结果。

### 现有源的情况

33 个源里产量和可用率差得很远（实测）：

| 类型 | 代表 | 说明 |
|---|---|---|
| **高匿专供** | Thordata、VPSLab、Proxmint、RelayGlass | 只抓 elite/anonymous 列表，277~917 条，质量最高 |
| **高匿大池** | Madeval、FusionProxies、Litportnet | 带匿名等级标签/合并去重，1400~8400 条 |
| 高产低质 | OpenProxyList、Proxy4Parsing、Geonode、Jetkai、B4RC0DE | 单轮 3000~10000 条，可用率 0.2%~1.4% |
| 高质量 | AdvancedName | 只有 300 条，可用率 12% |
| 少量 | ShiftyTR、KxDaili、Ihuan、Prxchk | 几十条 |

免费代理还有两类「假可用」，判定时要挡掉：**要求认证**（返回 407 `Proxy Authentication Required`，只有账号密码才放行）和**劫持页**（状态 200 但正文是它自己的 JS 跳转广告壳）。这两种现在都判为不可用，见 `probe/verdict.py` 的 `looks_hijacked()`。

原来那批国内站（daili66、kuaidaili、ip3366、xicidaili、zhandaye 等）已经不抓了：一部分真的关站/改版，一部分是页面结构变了导致 `parse` 取不到数据。这些站现在大多要登录或上了反爬，性价比很低。

想知道此刻每个源还能抓多少：`python3 tools/measure_crawlers.py`（只统计，不写库）。

## 开发

```bash
pip install ruff pytest
ruff check .      # 语法与风格检查，CI 跑的是同一条
pytest            # 冒烟测试：需要本机有 Redis，用 db 5 和独立前缀，不碰正在运行的池
```

CI 在 Python 3.9 / 3.12、Redis 5 / 7 上跑这两条命令。

## 目录

```
proxyproof/
  probe/        四态判定规则、探测端点、漏斗探测
  storages/     池存储（ZSET + hash + 新鲜度索引）
  processors/   getter / tester / server
  crawlers/     33 个代理源，public/ 下每个文件一个源
  schemas/      Proxy
  utils/        cn_ip.py（国内段判断，CN_ONLY 用）
  setting.py    全部配置
tests/                  冒烟测试（pytest）
tools/
  stop.py               停掉本项目所有进程
  measure_crawlers.py   量每个爬虫能抓多少条（不写库）
  eval_baseline.py      开发期的离线评测脚本（输入样本不入库，见文件头说明）
examples/usage.py       接入示例（含 /report 反馈）
run.py                  入口，--processor 可单独跑
ruff.toml · pytest.ini  lint 与测试配置
```

## 来源与致谢

本项目派生自 **[Python3WebSpider/ProxyPool](https://github.com/Python3WebSpider/ProxyPool)**（作者 [崔庆才 Germey](https://cuiqingcai.com/7048.html)，MIT 协议），最初的代理池设计与爬虫框架来自那里。如果你只是想理解"代理池是怎么工作的"，那篇原文比本 README 讲得更系统。

**保留的部分**

- `BaseCrawler` / `TextListCrawler` 爬虫框架与自动注册机制（33 个源都是这个模式）
- 用 Redis 有序集合存储代理的基本思路
- `/random`、`/count`、`/all` 的 API 形态

**重写的部分**

| 原实现 | 现在 | 为什么 |
|---|---|---|
| 二元判定（有效/无效），减分淘汰 | 四态（OK/BLOCKED/DEAD/UNKNOWN） | 原实现把"第三方探针超时"和"代理坏了"混为一谈，一次网络抖动能把整池减没 |
| 全量 ZSCAN 扫描，周期 20s | 到期队列 + 热队列 | 原实现的"周期"实际是"扫完耗时 + 20s"，池子一大就失控；且在 ZSCAN 中改分数会漏成员 |
| 一个全局分数 | 按目标（key）分别记分 | 代理的可用性是相对目标而言的，一个分数量化不了 |
| 可用即置 100，失败减 1 | EWMA × 延迟 × 纯度 | 100 分这一档没有区分度，抖动代理和岩石代理同分 |
| 分发时全量拉满分集合再随机 | SRANDMEMBER + power-of-two-choices | 5 万池下每次请求 54ms → 2.2ms |
| 无可用代理时降级返回低分代理 | 直接 503 | 发一个死代理比返回"暂时没有"更伤调用方 |
| 每轮直连取 httpbin 基线做匿名判定 | 进程内缓存一组基线 IP | 本机出口会在同一 /24 内轮换，单个 IP 比对会误判 |

感谢原作者把这个项目做到"能跑、能读、能扩展"的程度——没有那套爬虫框架和清晰的模块划分，这次的改造不会这么顺。

## 免责声明

**本项目仅用于技术学习与研究。**

1. **代理来源**：池中的代理全部抓取自互联网上的公开免费资源。本项目不生产、不购买、也不验证这些代理的合法性与归属。免费代理常被多人共用，可能被用于扫描、撞库等恶意行为，**其出口 IP 的信誉不由本项目控制**。

2. **不要传输敏感数据**：经免费代理传输的任何内容，理论上都可能被代理持有者记录或篡改。**严禁**通过本项目的代理提交账号密码、支付信息、身份证件、企业内部数据等敏感内容。

3. **控制请求频率**：本项目默认把探测目标设为 Cloudflare 的连通性端点（`cp.cloudflare.com`，返回 204、0 字节），就是为了不给任何第三方站点造成负担。**请勿把别人的内容站当作探针**——实测把某资讯站设为目标后，几万次探测会使对方对该 IP 限速。你自己在 `PROBE_TARGETS` 里配置的目标站，其访问频率与合规性由你负责。

4. **遵守目标站点规则**：使用代理访问任何站点时，请遵守该站点的 `robots.txt`、服务条款与当地法律法规。本项目不提供绕过访问控制、验证码、付费墙或反爬机制的能力。

5. **数据与隐私**：本项目不收集、不上传任何使用者数据。所有状态仅存于你本机的 Redis，日志仅写本地 `logs/` 目录。

6. **无担保**：软件按「原样」提供，不附带任何明示或暗示的担保。因使用本项目产生的任何直接或间接损失（包括但不限于 IP 被封、账号受限、法律纠纷），由使用者自行承担。

7. **合规使用**：请勿将本项目用于网络攻击、非法爬取、绕过地域限制获取受版权保护的内容，或任何违反所在地法律的活动。

如果你不接受上述条款，请停止使用并删除本项目。

## LICENSE

MIT
