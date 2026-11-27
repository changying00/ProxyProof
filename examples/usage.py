"""从代理池取代理并真实请求一次，失败就反馈给池子。

    python examples/usage.py [目标URL] [key]

要点：
  - /random 返回 503 表示池子暂时没有可用代理，应当跳过而不是把重试打满
  - 真实请求失败要调 /report，让池子立刻把它摘掉，不用等下一轮检测
"""
import sys

import requests

POOL = 'http://127.0.0.1:5555'
TARGET = sys.argv[1] if len(sys.argv) > 1 else 'http://cp.cloudflare.com/'
KEY = sys.argv[2] if len(sys.argv) > 2 else 'default'


def get_proxy(key=KEY):
    r = requests.get(f'{POOL}/random', params={'key': key}, timeout=5)
    if r.status_code == 503:
        return None
    r.raise_for_status()
    return r.text.strip()


def report(proxy, ok, key=KEY):
    try:
        requests.get(f'{POOL}/report',
                     params={'key': key, 'proxy': proxy, 'ok': int(ok)}, timeout=3)
    except requests.RequestException:
        pass


def crawl(url, proxy):
    p = {'http': f'http://{proxy}'}
    return requests.get(url, proxies=p, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})


def main():
    proxy = get_proxy()
    if not proxy:
        print('池子暂时没有可用代理（503），稍后再试')
        return
    print('拿到代理', proxy)
    try:
        r = crawl(TARGET, proxy)
    except requests.RequestException as e:
        print('请求失败', type(e).__name__)
        report(proxy, ok=False)
        return
    if r.status_code >= 400:
        print('目标返回', r.status_code, '→ 反馈失败')
        report(proxy, ok=False)
        return
    report(proxy, ok=True)
    print('成功', r.status_code, len(r.content), 'bytes')


if __name__ == '__main__':
    main()
