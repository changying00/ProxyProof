from proxyproof.crawlers.base_list import TextListCrawler

BASE_URL = 'https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/{list}'


class LitportnetCrawler(TextListCrawler):
    """
    Litportnet/free-proxy-list crawler, https://github.com/litportnet/free-proxy-list
    每几分钟验证，带延迟/在线率/匿名等级/ASN 等元数据
    """
    urls = [
        BASE_URL.format(list='http.txt'),   # HTTP 代理（含延迟/在线率/匿名等级）
    ]
