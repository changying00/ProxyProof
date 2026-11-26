from proxyproof.crawlers.base_list import TextListCrawler


BASE_URL = 'https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/{protocol}.txt'


class TheSpeedXCrawler(TextListCrawler):
    """
    TheSpeedX/PROXY-List crawler, https://github.com/TheSpeedX/PROXY-List
    纯文本列表，每行 ip:port，每天更新，HTTP/HTTPS 两种协议分开存放
    """
    urls = [
        BASE_URL.format(protocol='http'),
        BASE_URL.format(protocol='https'),
    ]


if __name__ == '__main__':
    crawler = TheSpeedXCrawler()
    for proxy in crawler.crawl():
        print(proxy)
