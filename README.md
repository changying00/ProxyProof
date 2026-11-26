# ProxyProof

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)
![](https://img.shields.io/badge/python-3.9%2B-brightgreen)
![](https://img.shields.io/badge/redis-5.0%2B-red)

简易高效的代理池，提供如下功能：

- 定时抓取免费代理网站，26 个源并发抓取，简易可扩展。
- 使用 Redis 存储代理，并按**目标**分别记录可用性。
- 定时探测，四态判定（可用 / 目标不通 / 死亡 / 未知），剔除不可用代理。
- 提供代理 API，只返回"刚刚确认过能用"的代理。

## 与常见代理池的区别

大部分免费代理池的判定是"能不能连上百度"。这在实际使用中几乎没有预测力：同一个代理可能连得上百度、却打不开你的目标站。

本项目的判定对象是 `(代理 × 目标 × 时刻)` 这个三元组：

- 每个 `key` 对应一组目标 URL，代理对每个 key 单独记分，互不影响。
- 只有"最近 `PROBE_MAX_AGE` 秒内确认可用"的代理会被发出去，否则直接返回 `503`。
- 判定分四态：`OK` / `BLOCKED`（代理活着但目标不通）/ `DEAD`（连不上）/ `UNKNOWN`（探针自己出问题）。`BLOCKED` 降权不删除，`UNKNOWN` 完全不扣分——避免第三方抖动把好代理误杀。

## 探测目标怎么选

**这是整套系统里最需要想清楚的一件事**：探测器会对目标发请求，池子越大，请求越多。

默认用的是 `http://cp.cloudflare.com/`——Cloudflare 专门为"连通性检测"提供的端点，返回 204、0 字节，面向海量探测设计。拿它当探针，等于不占用任何人的带宽，也不会把谁打限速。

**不要拿别人的内容站当探针。** 我实测过：拿某资讯站（首页 271KB）当目标，跑几万个代理之后，对方直接把我本机 IP 限速到 11 秒响应。这不是"测试"，这是小型 CC。

所以推荐的分工是：

| key | 目标 | 用途 |
|---|---|---|
| `default` | `http://cp.cloudflare.com/` | 通用池：只验证"代理能正常代理 HTTP" |
| 你的站 | 你自己的目标页 | 专用池：额外验证"代理能打开这个站" |

```ini
PROBE_TARGETS={"default":[{"url":"http://cp.cloudflare.com/","min_len":0}],"mysite":[{"url":"https://你的站/","min_len":3000}]}
```

然后 `GET /random?key=mysite`。两个池子的分数完全独立：一个代理在 `default` 里可能 95 分，在你的站上 0 分。

如果你有服务器，最稳的做法是自己起一个端点（返回 204 或一句固定文本），把它写进 `PROBE_TARGETS`——完全不依赖第三方。

## 使用前注意

免费代理的可用性很低。实测 3000~10000 个代理里，能正常做 HTTP 代理的通常只有几十个（0.5%~5%，取决于目标站的容忍度）。

如果目的是尽快完成爬取任务，建议对接付费代理；如果目的是学习怎么搭代理池，继续往下看。

## 使用准备

```bash
git clone git@github.com:changying00/ProxyProof.git
cd ProxyProof
```

## 使用要求

- Python >= 3.9
- Redis 5.0 及以上（不依赖 6.2 的 `ZRANDMEMBER`）

## 安装和运行

### 安装和配置 Redis

本地安装 Redis、远程 Redis 都可以，只要能正常连接即可。

### 安装依赖包

```bash
python3 -m venv .venv
source .venv/bin/activate      # Windows 用 .venv\Scripts\activate
pip install -r requirements.txt
```

### 运行代理池

配置好环境变量（可以写进项目根目录的 `.env`，见下方「可配置项」）之后，一条命令启动全部：

```bash
python3 run.py
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

刚启动时池子是空的：getter 要先爬一轮（约 1 分钟），tester 再逐个探测，`fresh` 才会从 0 涨上来（2~4 分钟）。

### 停止

```bash
python3 tools/stop.py
```

不要用 Ctrl+C 或任务管理器。调度器 spawn 出的子进程命令行里没有项目路径，手动 kill 容易留下孤儿进程继续抓取，还占着端口。

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
    proxies = {'http': 'http://' + proxy, 'https': 'http://' + proxy}
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

```
GET http://localhost:5555/random?key=mysite
GET http://localhost:5555/count?key=mysite
```

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

## 可配置项

所有配置通过环境变量设置，可以写进项目根目录的 `.env`（`environs` 会自动读取）。

### 开关

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `ENABLE_GETTER` | `true` | 是否启用获取器 |
| `ENABLE_TESTER` | `true` | 是否启用检测器 |
| `ENABLE_SERVER` | `true` | 是否启用 API 服务 |

### 环境

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `APP_ENV` | `dev` | 可选 `dev` / `test` / `prod` |
| `APP_DEBUG` | `dev` 下为 `true` | Flask 调试模式 |

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
| `PROBE_TARGETS` | `{"default":[{"url":"http://cp.cloudflare.com/","min_len":0}]}` | 目标分组，JSON |
| `PROBE_IDENTITY_URLS` | `["http://ip.3322.net/","http://myip.ipip.net/"]` | 身份探针回退链，返回出口 IP |
| `PROBE_TCP_TIMEOUT` | `0.8` | TCP 探测超时（秒） |
| `PROBE_TIMEOUT_IDENTITY` | `3` | 身份探测超时 |
| `PROBE_TIMEOUT_TARGET` | `6` | 目标探测超时 |
| `PROBE_CONCURRENCY` | `100` | 探测并发数 |
| `PROBE_BATCH` | `200` | 单批探测数量 |

`min_len` 是响应体长度下限，用来排掉挑战页和空壳页。204 端点设为 0。

### 池容量与调度

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `PROXY_NUMBER_MAX` | `3000` | 池子上限 |
| `PROXY_SCORE_INIT` | `10` | 新代理入池初始分 |
| `INTRODUCE_WINDOW` | `600` | 新代理首次检测打散窗口（秒） |
| `CYCLE_TESTER` | `20` | 检测器每轮的时间预算（秒） |
| `CYCLE_GETTER` | `300` | 抓取周期（秒） |
| `PROBE_MAX_AGE` | `180` | 分发新鲜度闸门（秒） |
| `GET_TIMEOUT` | `10` | 爬虫请求超时 |

> 上限不是越大越好。`fresh` 的天花板 ≈ 检测吞吐 × 可用率 × 新鲜窗口，和池子大小无关。
> 池子开到 10000 时 `fresh` 只有 50 左右，3000 时也有 40 左右——多出来的两万个代理只会摊薄检测频率。

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

26 个源里产量和可用率差得很远（实测）：

| 类型 | 代表 | 说明 |
|---|---|---|
| 高产低质 | OpenProxyList、Proxy4Parsing、Geonode、Jetkai、B4RC0DE | 单轮 3000~10000 条，可用率 0.2%~1.4% |
| 高质量 | AdvancedName | 只有 300 条，可用率 12% |
| 少量 | ShiftyTR、KxDaili、Ihuan、Prxchk | 几十条 |

原来那批国内站（daili66、kuaidaili、ip3366、xicidaili、zhandaye 等）已经不抓了：一部分真的关站/改版，一部分是页面结构变了导致 `parse` 取不到数据。这些站现在大多要登录或上了反爬，性价比很低。

## 目录

```
proxyproof/
  probe/        判定规则、探测端点、漏斗探测
  storages/     池存储（ZSET + hash + 新鲜度索引）
  processors/   getter / tester / server
  crawlers/     26 个代理源，public/ 下每个文件一个源
  schemas/      Proxy
  setting.py    全部配置
tools/
  stop.py               停掉本项目所有进程
  measure_crawlers.py   量每个爬虫能抓多少条（不写库）
  eval_baseline.py      按 EVAL_STANDARD 算评测指标
  samples/              抽样原始数据（本地评测用，已 gitignore）
examples/usage.py       接入示例（含 /report 反馈）
run.py                  入口，--processor 可单独跑
```

## 来源与致谢

本项目派生自 **[Python3WebSpider/ProxyPool](https://github.com/Python3WebSpider/ProxyPool)**（作者 [崔庆才 Germey](https://cuiqingcai.com/7048.html)，MIT 协议），最初的代理池设计与爬虫框架来自那里。如果你只是想理解"代理池是怎么工作的"，那篇原文比本 README 讲得更系统。

**保留的部分**

- `BaseCrawler` / `TextListCrawler` 爬虫框架与自动注册机制（26 个源都是这个模式）
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
