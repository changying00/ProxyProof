from proxyproof.crawlers.base_list import TextListCrawler


BASE_URL = 'https://raw.githubusercontent.com/zloi-user/hideip.me/main/{protocol}.txt'


class HideipMeCrawler(TextListCrawler):
    """
    zloi-user/hideip.me crawler, https://github.com/zloi-user/hideip.me
    列表里带 `ip:port:国家代码` 后缀，解析器会忽略尾部字段
    """
    urls = [
        BASE_URL.format(protocol='http'),
        BASE_URL.format(protocol='https'),
    ]


if __name__ == '__main__':
    crawler = HideipMeCrawler()
    for proxy in crawler.crawl():
        print(proxy)
