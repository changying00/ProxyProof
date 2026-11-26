from proxyproof.crawlers.base_list import TextListCrawler


# 带 scheme 前缀（http://1.2.3.4:8080），解析器已支持
BASE_URL = 'https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/http/data.txt'


class ProxiflyCrawler(TextListCrawler):
    """
    proxifly/free-proxy-list crawler, https://github.com/proxifly/free-proxy-list
    走 jsDelivr CDN，国内访问比 raw.githubusercontent.com 稳定
    """
    urls = [BASE_URL]
    max_proxies = 3000


if __name__ == '__main__':
    crawler = ProxiflyCrawler()
    for proxy in crawler.crawl():
        print(proxy)
