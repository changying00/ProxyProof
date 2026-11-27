from proxyproof.crawlers.base_list import TextListCrawler

BASE_URL = 'https://raw.githubusercontent.com/FusionProxies/free-proxy-list/main/proxies/{list}'


class FusionProxiesCrawler(TextListCrawler):
    """
    FusionProxies/free-proxy-list crawler, https://github.com/FusionProxies/free-proxy-list
    每 30 分钟合并 5 个公共列表去重，带国家/协议/匿名等级
    """
    urls = [
        BASE_URL.format(list='http.txt'),   # HTTP 代理（去重合并）
    ]
