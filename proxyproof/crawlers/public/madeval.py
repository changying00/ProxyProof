from proxyproof.crawlers.base_list import TextListCrawler

BASE_URL = 'https://raw.githubusercontent.com/MADEVAL/free-proxy-list/main/{list}'


class MadevalCrawler(TextListCrawler):
    """
    MADEVAL/free-proxy-list crawler, https://github.com/MADEVAL/free-proxy-list
    自动重建，1M+ 地址池，带 elite/anonymous 标签，每天更新
    """
    urls = [
        BASE_URL.format(list='elite.txt'),       # elite 高匿（~12000 条）
        BASE_URL.format(list='anonymous.txt'),   # anonymous 匿名（~3700 条）
    ]
