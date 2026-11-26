from proxyproof.crawlers.base_list import TextListCrawler


BASE_URL = 'https://api.openproxylist.xyz/{protocol}.txt'


class OpenProxyListCrawler(TextListCrawler):
    """
    openproxylist crawler, http://openproxylist.xyz/
    纯文本列表，数千条，按协议分文件
    """
    urls = [
        BASE_URL.format(protocol='http'),
        BASE_URL.format(protocol='https'),
    ]


if __name__ == '__main__':
    crawler = OpenProxyListCrawler()
    for proxy in crawler.crawl():
        print(proxy)
