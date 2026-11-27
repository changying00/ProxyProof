from proxyproof.crawlers.base_list import TextListCrawler

BASE_URL = 'https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/{list}'


class ThordataCrawler(TextListCrawler):
    """
    Thordata/awesome-free-proxy-list crawler, https://github.com/Thordata/awesome-free-proxy-list
    每日验证，带匿名等级/延迟/存续天数，专抓高匿和稳定列表
    """
    urls = [
        BASE_URL.format(list='high-anon.txt'),   # elite 高匿（不泄露 IP 不暴露代理）
        BASE_URL.format(list='stable.txt'),      # 多日存活的稳定代理
        BASE_URL.format(list='top-trusted.txt'), # 快速 + 高匿 + 存活 ≥2 天
    ]
