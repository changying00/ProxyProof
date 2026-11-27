from proxyproof.crawlers.base_list import TextListCrawler

BASE_URL = 'https://raw.githubusercontent.com/relayglass/free-proxy-list/main/anonymity/{level}/{protocol}/{protocol}.txt'


class RelayGlassCrawler(TextListCrawler):
    """
    RelayGlass/free-proxy-list crawler, https://github.com/relayglass/free-proxy-list
    每 5 分钟验证，按匿名等级/协议分目录，只抓 elite HTTP
    """
    urls = [
        BASE_URL.format(level='elite', protocol='http'),     # elite HTTP（~315 条）
        BASE_URL.format(level='elite', protocol='https'),    # elite HTTPS（支持 CONNECT）
    ]
