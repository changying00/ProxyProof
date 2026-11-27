"""验证请求到底走没走代理。用法：python verify_proxy.py"""
import requests

POOL = 'http://8.220.246.112:5555'
ECHO = 'http://ip-api.com/json/?fields=query,country,proxy,hosting'
TARGET = 'https://read.zongheng.com/chapter/1516636/93722332.html'

s = requests.Session()
s.trust_env = False          # 忽略系统代理，否则测出来的是 Clash 的 IP
s.headers['User-Agent'] = 'Mozilla/5.0'


def my_ip(proxy=None):
    """经（或不经）代理请求回显服务，返回目标站看到的 IP"""
    p = {'http': f'http://{proxy}', 'https': f'http://{proxy}'} if proxy else None
    r = s.get(ECHO, proxies=p, timeout=10)
    return r.json()


if __name__ == '__main__':
    direct = my_ip()
    print(f'[直连]  出口 IP = {direct["query"]}  {direct.get("country")}')

    for i in range(5):
        try:
            r = s.get(f'{POOL}/random', timeout=5)
            if r.status_code != 200:
                print(f'[{i}] 池子返回 {r.status_code}，无可用代理')
                continue
            proxy = r.text.strip()

            got = my_ip(proxy)
            same = got['query'] == direct['query']
            print(f'[{i}] {proxy:22s} -> {got["query"]:16s} '
                  f'{"❌ 还是本机 IP，代理没生效" if same else "✅ 已换 IP，代理生效"}')
        except ValueError:
            print(f'[{i}] 返回的不是 JSON —— 代理把响应改写了（劫持页/错误页），不能用')
        except requests.exceptions.ConnectTimeout:
            print(f'[{i}] 代理连接超时')
        except Exception as e:
            print(f'[{i}] {type(e).__name__}: {str(e)[:60]}')
