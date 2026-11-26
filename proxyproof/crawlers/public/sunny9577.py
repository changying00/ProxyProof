from proxyproof.crawlers.base_list import TextListCrawler

BASE_URL = 'https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/proxies.txt'


class Sunny9577Crawler(TextListCrawler):
    """
    sunny9577/proxy-scraper crawler, https://github.com/sunny9577/proxy-scraper
    由多个公开源聚合而成，实测有效率较高
    """
    urls = [BASE_URL]


if __name__ == '__main__':
    crawler = Sunny9577Crawler()
    for proxy in crawler.crawl():
        print(proxy)
