# ProxyProof

[![CI](https://github.com/changying00/ProxyProof/actions/workflows/ci.yml/badge.svg)](https://github.com/changying00/ProxyProof/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)
![](https://img.shields.io/badge/python-3.9%2B-brightgreen)
![](https://img.shields.io/badge/redis-5.0%2B-red)

[简体中文](./README.md)

A proxy pool that verifies free proxies against your target site and serves them over an HTTP API.

```console
$ curl localhost:5555/random            # one proxy confirmed working moments ago
39.109.113.97:4090

$ curl localhost:5555/stats             # state of the pool
{"default": {"total": 2899, "fresh": 149, "due": 841,
             "verdicts": {"OK": 167, "BLOCKED": 73, "DEAD": 2094, "UNKNOWN": 172}}}
```

`fresh` counts the proxies confirmed usable within the last `PROBE_MAX_AGE` seconds, and `/random` hands out nothing else. When there are none it returns `503` instead of an unverified proxy.

- Crawls 26 public proxy sources on a schedule, stores them in Redis, serves them over HTTP (`/random` `/all` `/count` `/stats` `/report`)
- Scores each proxy per target site with a four-state verdict; only recently confirmed proxies are served
- Probes through a funnel (TCP → identity → target), so a dead proxy is out in 0.8 s. The default probe is Cloudflare's connectivity endpoint, which costs nobody any bandwidth

## Who it is for

- **Good fit**: you want to understand how a proxy pool is designed, you have a small scraping job, or you don't want to pay for proxies.
- **Bad fit**: production-scale crawling. Only a few percent of free proxies work at any given moment (measured on my machine: out of 3,000 proxies, somewhere between several dozen and three hundred are usable). At that scale, buying proxies is the cheaper option.

## Quick start

Requires Python >= 3.9 and Redis 5.0 or newer (it does not rely on `ZRANDMEMBER`, which only arrived in 6.2).

```bash
git clone https://github.com/changying00/ProxyProof.git
cd ProxyProof
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # set REDIS_HOST / REDIS_PASSWORD if Redis is elsewhere
python3 run.py
```

The pool starts empty: the getter crawls for about a minute, the tester then works through the results, and `fresh` climbs over 2–4 minutes. After that:

```bash
curl http://127.0.0.1:5555/random
```

The log looks like this:

```
2026-11-26 20:19:43 | INFO | proxyproof.scheduler:run:100 - starting proxyproof...
2026-11-26 20:19:43 | INFO | proxyproof.scheduler:run:104 - starting tester...
2026-11-26 20:19:43 | INFO | proxyproof.scheduler:run:110 - starting getter...
2026-11-26 20:19:43 | INFO | proxyproof.scheduler:run:116 - starting server...
2026-11-26 20:19:50 | INFO | proxyproof.processors.tester:_pass:40 - [default] probed 200 fresh=12 total=3000
```

You can also run a single process on its own:

```bash
python3 run.py --processor getter
python3 run.py --processor tester
python3 run.py --processor server
```

**To stop**, run `python3 tools/stop.py`. Don't use Ctrl+C or the task manager: the scheduler spawns child processes whose command lines don't contain the project path, so killing them by hand tends to leave orphans that keep crawling and hold the port.

`.env` lists every setting with a comment on each line; usually only `REDIS_HOST` / `REDIS_PASSWORD` need changing. `.env` is git-ignored, so a password in it won't be committed.

## How it differs from the usual proxy pool

Most proxy pools ask "can this proxy reach Baidu". That predicts almost nothing about the site you actually care about: reaching Baidu doesn't mean it can open your target.

ProxyProof scores `(proxy × target × moment)`:

- Each `key` maps to a group of target URLs, and every proxy is scored separately for each key. See [Proxies per target site](#proxies-per-target-site).
- The verdict has four states: `OK` / `BLOCKED` (proxy alive, target unreachable) / `DEAD` (cannot connect) / `UNKNOWN` (the probe itself failed). `BLOCKED` lowers the score without removing the proxy, and `UNKNOWN` leaves the score alone, so a hiccup on a third-party endpoint can't wipe out good proxies.
- Only proxies confirmed usable within the last `PROBE_MAX_AGE` seconds are served; otherwise `503`.

How to choose a probe target, and why the default is `cp.cloudflare.com`: [Choosing probe targets](#choosing-probe-targets).

## Usage

```bash
curl http://127.0.0.1:5555/random
```

Using it from a program:

```python
import requests

proxyproof_url = 'http://127.0.0.1:5555/random'
target_url = 'http://your-target/'

def get_random_proxy():
    r = requests.get(proxyproof_url, timeout=5)
    if r.status_code == 503:        # no usable proxy right now
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

A complete example, including the `/report` feedback call, is in [examples/usage.py](./examples/usage.py).

### Several proxies at once

```
GET http://localhost:5555/random?count=5
```

Without `count`, or with `count=1`, a single proxy is returned; a `count` larger than the number available returns all of them. Combine with `key`.

### Proxies per target site

Add a `key` to `PROBE_TARGETS` first (see [Choosing probe targets](#choosing-probe-targets)), then:

```
GET http://localhost:5555/random?key=mysite
GET http://localhost:5555/count?key=mysite
```

### Reporting results

One real failure from the caller carries more information than ten probes:

```
GET http://localhost:5555/report?proxy=1.2.3.4:80&ok=0
```

A failure removes the proxy from the fresh set immediately, without waiting for the next probe; a success refresh its freshness.

### Pool status

```
GET http://localhost:5555/stats
```

Returns, for each key, `total` (proxies in the pool), `fresh` (fresh and usable), `due` (waiting to be probed) and `verdicts` (distribution of the latest verdicts).

## Configuration

Everything is configured through environment variables, which can be written to a `.env` in the project root (`environs` reads it automatically). The full list with comments is in [.env.example](./.env.example).

### Switches

| Variable | Default | Description |
|---|---|---|
| `ENABLE_GETTER` | `true` | run the getter |
| `ENABLE_TESTER` | `true` | run the tester |
| `ENABLE_SERVER` | `true` | run the API server |

### Environment

| Variable | Default | Description |
|---|---|---|
| `APP_ENV` | `dev` | `dev` / `test` / `prod` |
| `APP_DEBUG` | `true` under `dev` | Flask debug mode |
| `APP_PROD_METHOD` | `gevent` | WSGI container under `prod`: `gevent` / `tornado` / `meinheld` (install the latter two yourself) |

### Redis

| Variable | Default | Description |
|---|---|---|
| `REDIS_HOST` | `127.0.0.1` | Redis host |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_PASSWORD` | empty | Redis password |
| `REDIS_DB` | `0` | Redis database number |
| `REDIS_CONNECTION_STRING` | empty | connection string; takes precedence over the four above |

### Targets and probing

| Variable | Default | Description |
|---|---|---|
| `PROBE_TARGETS` | `{"default":[{"url":"http://cp.cloudflare.com/","min_len":0}]}` | target groups, JSON |
| `PROBE_IDENTITY_URLS` | `["http://ip.3322.net/","http://myip.ipip.net/"]` | identity-probe fallback chain; each returns the exit IP |
| `PROBE_TCP_TIMEOUT` | `0.8` | TCP connect timeout (seconds) |
| `PROBE_TIMEOUT_IDENTITY` | `3` | identity probe timeout |
| `PROBE_TIMEOUT_TARGET` | `6` | target probe timeout |
| `PROBE_CONCURRENCY` | `100` | concurrent probes |
| `PROBE_BATCH` | `200` | proxies probed per batch |

`min_len` is the minimum response body length, used to filter out challenge pages and empty shells. Set it to 0 for 204 endpoints.

### Pool size and scheduling

| Variable | Default | Description |
|---|---|---|
| `PROXY_NUMBER_MAX` | `3000` | pool capacity |
| `PROXY_SCORE_INIT` | `10` | initial score of a new proxy |
| `INTRODUCE_WINDOW` | `900` | window (seconds) over which new proxies are spread for their first probe |
| `CYCLE_TESTER` | `20` | tester time budget per cycle (seconds) |
| `CYCLE_GETTER` | `300` | crawl interval (seconds) |
| `PROBE_MAX_AGE` | `180` | freshness gate for serving (seconds) |
| `GET_TIMEOUT` | `10` | crawler request timeout |

> A bigger cap is not better. The ceiling on `fresh` is roughly probe throughput × usable rate × freshness window, and has nothing to do with pool size: raise the cap and every proxy simply waits longer between re-probes, so the extra proxies only dilute the probing.

### API and logging

| Variable | Default | Description |
|---|---|---|
| `API_HOST` | `0.0.0.0` | use `127.0.0.1` for local-only access |
| `API_PORT` | `5555` | API port |
| `API_THREADED` | `true` | Flask threaded mode |
| `API_KEY` | empty | when set, requests must carry an `API-KEY` header |
| `ENABLE_LOG_FILE` | `true` | write log files |
| `LOG_ROTATION` | `500MB` | log rotation size |
| `LOG_RETENTION` | `1 week` | log retention |

## Choosing probe targets

**This is the one thing in the whole system worth thinking through carefully**: the tester sends requests to the target, and the bigger the pool, the more requests.

The default is `http://cp.cloudflare.com/`, an endpoint Cloudflare provides specifically for connectivity checks. It returns 204 with zero bytes and is built for high-volume probing, so using it as a probe costs nobody bandwidth and gets nobody rate-limited.

**Don't use someone else's content site as a probe.** I tried it: with a news site (271 KB home page) as the target, after tens of thousands of proxies the site rate-limited my IP to 11-second responses. That isn't "testing", it's a small-scale flood.

The recommended split is therefore:

| key | target | purpose |
|---|---|---|
| `default` | `http://cp.cloudflare.com/` | general pool: only verifies "the proxy can proxy HTTP" |
| your site | your own target page | dedicated pool: additionally verifies "the proxy can open this site" |

```ini
PROBE_TARGETS={"default":[{"url":"http://cp.cloudflare.com/","min_len":0}],"mysite":[{"url":"https://your-site/","min_len":3000}]}
```

Then call `GET /random?key=mysite`. The two pools are scored completely independently: a proxy may score 95 under `default` and 0 on your site.

If you have a server, the most robust option is to host your own endpoint (returning 204 or a fixed line of text) and put it in `PROBE_TARGETS`, so you don't depend on any third party.

## Adding a proxy source

Create a file under `proxyproof/crawlers/public/` that subclasses `BaseCrawler`; it is picked up automatically:

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

If the source is a plain-text list of one `ip:port` per line, subclass `TextListCrawler` from `proxyproof/crawlers/base_list.py` and declare only `urls`.

Crawler requests never use the system proxy (`trust_env=False`), so the results don't depend on whether a local proxy such as Clash is running.

### The current sources

Yield and usable rate vary widely across the 26 sources (measured):

| Type | Examples | Notes |
|---|---|---|
| High volume, low quality | OpenProxyList, Proxy4Parsing, Geonode, Jetkai, B4RC0DE | 3,000–10,000 per round, 0.2%–1.4% usable |
| High quality | AdvancedName | only 300 proxies, 12% usable |
| Small | ShiftyTR, KxDaili, Ihuan, Prxchk | a few dozen |

The Chinese sites the upstream project used (daili66, kuaidaili, ip3366, xicidaili, zhandaye, …) are no longer crawled: some have shut down or redesigned, and on the rest the page structure changed so `parse` returns nothing. Most of them now require a login or have anti-scraping in place, which makes them a poor trade.

To see what each source yields right now: `python3 tools/measure_crawlers.py` (counts only, writes nothing).

## Development

```bash
pip install ruff pytest
ruff check .      # lint; CI runs the same command
pytest            # smoke tests: needs a local Redis, uses db 5 and its own key prefix, never touches a running pool
```

CI runs both commands on Python 3.9 / 3.12 against Redis 5 / 7.

## Layout

```
proxyproof/
  probe/        four-state verdict rules, probe endpoints, funnel probing
  storages/     pool storage (ZSET + hash + freshness index)
  processors/   getter / tester / server
  crawlers/     26 proxy sources, one file per source under public/
  schemas/      Proxy
  setting.py    all configuration
tests/                  smoke tests (pytest)
tools/
  stop.py               stop every process of this project
  measure_crawlers.py   count what each crawler yields (writes nothing)
  eval_baseline.py      offline evaluation script from development (input samples are not committed; see the file header)
examples/usage.py       integration example (with /report feedback)
run.py                  entry point; --processor runs one process
ruff.toml · pytest.ini  lint and test configuration
```

## Origin and credits

This project is derived from **[Python3WebSpider/ProxyPool](https://github.com/Python3WebSpider/ProxyPool)** by [Germey (崔庆才)](https://cuiqingcai.com/7048.html), under the MIT license; the original proxy-pool design and crawler framework come from there. If you simply want to understand how a proxy pool works, [his article](https://cuiqingcai.com/7048.html) is more systematic than this README.

**Kept from the original**

- The `BaseCrawler` / `TextListCrawler` framework and automatic registration (all 26 sources use it)
- The idea of storing proxies in a Redis sorted set
- The shape of the `/random`, `/count` and `/all` API

**Rewritten**

| Original | Now | Why |
|---|---|---|
| Binary verdict (usable / unusable), score decay | Four states (OK / BLOCKED / DEAD / UNKNOWN) | The original conflated "the third-party probe timed out" with "the proxy is broken", so one network hiccup could drain the whole pool |
| Full ZSCAN every 20 s | Due queue + hot queue | The original "period" was really "scan time + 20 s", which falls apart on a large pool; changing scores mid-ZSCAN also skips members |
| One global score | A score per target (key) | Usability is relative to the target; a single number can't express it |
| Any success sets 100, each failure −1 | EWMA × latency × purity | A score of 100 has no resolution: a flapping proxy and a rock-solid one tie |
| Fetch all top-scored members, then random | SRANDMEMBER + power-of-two-choices | 54 ms → 2.2 ms per request on a 50k pool |
| Fall back to low-score proxies when none are fresh | Return 503 | Handing out a dead proxy hurts the caller more than "nothing available right now" |
| Fetch the httpbin baseline every round for anonymity | Cache a set of baseline IPs in-process | The local egress IP rotates within one /24, so comparing against a single IP misfires |

Thanks to the original author for making the project something that runs, reads well and extends easily. Without that crawler framework and the clean module boundaries, this rewrite would not have gone so smoothly.

## Disclaimer

**This project is for technical learning and research only.**

1. **Proxy sources**: every proxy in the pool is crawled from publicly available free lists on the internet. This project neither produces nor purchases proxies, and does not verify their legality or ownership. Free proxies are shared by many people and may be abused for scanning or credential stuffing; **the reputation of their exit IPs is outside this project's control**.

2. **Never send sensitive data**: anything routed through a free proxy can, in principle, be logged or tampered with by whoever runs the proxy. **Never** send passwords, payment details, identity documents or internal company data through proxies from this project.

3. **Keep request rates in check**: the default probe target is Cloudflare's connectivity endpoint (`cp.cloudflare.com`, 204 with zero bytes) precisely so that no third-party site carries any load. **Do not use someone else's content site as a probe**: in my tests, after tens of thousands of probes against a news site, that site rate-limited the IP. You are responsible for the request rate and the legality of the targets you configure in `PROBE_TARGETS`.

4. **Respect the target's rules**: when accessing any site through a proxy, follow its `robots.txt`, terms of service and local law. This project does not help bypass access controls, CAPTCHAs, paywalls or anti-scraping measures.

5. **Data and privacy**: this project collects and uploads nothing. All state lives in your own Redis; logs are written only to the local `logs/` directory.

6. **No warranty**: the software is provided "as is", without warranty of any kind. You bear sole responsibility for any direct or indirect loss arising from its use, including but not limited to banned IPs, restricted accounts or legal disputes.

7. **Lawful use**: do not use this project for attacks, unlawful scraping, circumventing geo-restrictions to obtain copyrighted content, or anything else prohibited by the laws that apply to you.

If you do not accept these terms, stop using the project and delete it.

## LICENSE

MIT
