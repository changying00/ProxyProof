from proxyproof.crawlers.base_list import TextListCrawler

BASE_URL = 'https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/{protocol}.txt'


class MuRongPIGCrawler(TextListCrawler):
    """
    MuRongPIG/Proxy-Master crawler, https://github.com/MuRongPIG/Proxy-Master
    列表很大，用 max_proxies 截断，避免单源吃掉整轮抓取
    """
    urls = [
        BASE_URL.format(protocol='http'),
        BASE_URL.format(protocol='https'),
    ]
    max_proxies = 3000


if __name__ == '__main__':
    crawler = MuRongPIGCrawler()
    for proxy in crawler.crawl():
        print(proxy)
