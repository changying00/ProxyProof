from proxyproof.crawlers.base_list import TextListCrawler

BASE_URL = 'https://raw.githubusercontent.com/VPSLabCloud/VPSLab-Free-Proxy-List/main/{list}'


class VPSLabCrawler(TextListCrawler):
    """
    VPSLabCloud/VPSLab-Free-Proxy-List crawler, https://github.com/VPSLabCloud/VPSLab-Free-Proxy-List
    每 15 分钟更新，按匿名等级/协议分文件，只抓 elite 高匿
    """
    urls = [
        BASE_URL.format(list='all_elite.txt'),       # 全协议 elite（~1000 条）
        BASE_URL.format(list='http_elite.txt'),      # HTTP elite（~189 条）
        BASE_URL.format(list='http_ssl_elite.txt'),  # HTTP SSL elite（~80 条，支持 CONNECT）
    ]
