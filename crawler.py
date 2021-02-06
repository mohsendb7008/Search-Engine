from classes import *

config = {
    "max_crawl_depth": 5,
    "crawl_sleep_seconds": 0.2,
    "base_url": "http://lms.ui.ac.ir",
    "database_file": "data.db",
    "log_file": "crawler_log.txt"
}

if __name__ == '__main__':
    crawler = Crawler(config)
    crawler.crawl()

