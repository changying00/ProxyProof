from proxyproof.crawlers.base_list import TextListCrawler

BASE_URL = 'https://raw.githubusercontent.com/proxmint/free-proxy-list/main/proxies/{list}'


class ProxmintCrawler(TextListCrawler):
    """
    Proxmint/free-proxy-list crawler, https://github.com/proxmint/free-proxy-list
    每 30 分钟重新验证，带匿名等级/延迟/在线率，只抓 elite 高匿
    """
    urls = [
        BASE_URL.format(list='elite.txt'),     # elite 高匿（无泄露）
        BASE_URL.format(list='http.txt'),      # HTTP 代理（通用）
        BASE_URL.format(list='https.txt'),     # HTTPS 代理
    ]
