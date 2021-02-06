import re, json
from flask import Flask
from flask import request
from threading import Thread
from classes import *
from datetime import datetime

app = Flask(__name__)

crawl_config = {
    "max_crawl_depth": 5,
    "crawl_sleep_seconds": 0.2,
    "database_file": "data.db",
    "log_file": None
}


def use_crawler(config: dict):
    crawler = Crawler(config)
    crawler.crawl()


valid_url_regex = re.compile(
        r'^(?:http|ftp)s?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)


@app.route('/submit_url/')
def submit_url():
    result = {}
    args = dict(request.args)
    if 'url' not in args:
        result['result'] = False
        result['message'] = 'No url indicated!'
    elif valid_url_regex.match(args['url']) is None:
        result['result'] = False
        result['message'] = 'Indicated url is not valid!'
    else:
        config = crawl_config.copy()
        url = args['url']
        url = url[:-1] if url[-1] == '/' else url
        config['base_url'] = url
        log_file = url + '_crawl_log.txt'
        config['log_file'] = 'logs/' + log_file.replace('http://', '').replace('https://', '').replace('www.', '').replace('//', '')
        Thread(target=use_crawler, args=(config,)).start()
        result['result'] = True
        result['message'] = 'Url submitted successfully!'
    return json.dumps(result)


search_config = {
    "database_file": "data.db",
    "log_file": None
}


def use_search_engine(config: dict):
    search_engine = SearchEngine(config)
    return search_engine.search_all(config['q'])


@app.route('/search/')
def search():
    result = {}
    args = dict(request.args)
    if 'q' not in args:
        result['result'] = False
        result['message'] = 'No q(keywords) indicated!'
    else:
        config = search_config.copy()
        config['q'] = ' '.join(args['q'].split(','))
        config['log_file'] = 'logs/' + str(datetime.now()) + "_search_log.txt"
        links = use_search_engine(config)
        result['result'] = True
        result['message'] = 'Search completed successfully!'
        result['links'] = links
    return json.dumps(result)


@app.route('/urls/')
def urls():
    return {'urls': crawled_urls('data.db')}


if __name__ == '__main__':
    app.run()
