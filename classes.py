import requests, sqlite3
from collections import Counter
from html.parser import HTMLParser
from time import sleep
from nltk import edit_distance
from string import punctuation
from bs4 import BeautifulSoup
from nltk import PorterStemmer


class Logger:

    """
    If programmer only wants to print into console and skip logging, should use an empty argument constructor.
    """
    def __init__(self, log_file_address: str = None):
        self.log_file_address = log_file_address
        self.log_file = open(self.log_file_address, 'w') if self.log_file_address else None

    def log(self, message: str, end: str = '\n'):
        print(message, end=end)
        if self.log_file:
            self.log_file.write(message + end)

    def flush(self):
        if self.log_file:
            self.log_file.flush()


def form_fill(inputs: list, database_file: str):
    """
    :param inputs: A list of field names
    :param database_file: Database file address with FormFill table
    :return: A dict of field names to field values based on maximum matching(minimum edit distance) with FormFill table data
    """
    conn = sqlite3.connect(database_file)
    cur = conn.cursor()
    cur.execute(''' SELECT * FROM FormFill ''')
    # List of tuple of Field and Value:
    fields = cur.fetchall()
    outputs = {}
    for input in inputs:
        min_match, min_match_value = fields[0], edit_distance(input, fields[0][0])
        for field in fields:
            distance = edit_distance(input, field[0])
            if distance < min_match_value:
                min_match = field
                min_match_value = distance
        outputs[input] = min_match[1]
    return outputs


# Form filling supported input types:
input_types = ['text', 'password', 'email', 'number', 'search', 'tel']


class LinkExtractor(HTMLParser):

    def __init__(self, html_text: str, logger: Logger, database_file: str):
        super().__init__()
        self.html_text = html_text
        self.logger = logger
        self.database_file = database_file
        self.links = set()
        # List of tuple of link and dict of data(body):
        self.forms = []
        # Current form dict of data:
        self.current_form_data = None
        self.follow = True
        self.index = True

    def error(self, message: str):
        self.logger.log(message)

    def extract(self):
        self.feed(self.html_text)
        if not self.follow:
            self.links.clear()
            self.forms.clear()
        return self.links, self.forms

    def handle_starttag(self, tag, attrs_):
        attrs = dict(attrs_)
        if self.follow:
            # Checking for robots meta tag:
            if tag == 'meta':
                if 'name' in attrs and 'content' in attrs and attrs['name'] == 'robots':
                    follow_index_list = attrs['content'].split(', ')
                    if 'nofollow' in follow_index_list:
                        self.follow = False
                        self.logger.log('This page should not be followed.')
                    if 'noindex' in follow_index_list:
                        self.index = False
                        self.logger.log('This page should not be indexed.')
                    self.logger.flush()
            # Extracting links:
            elif tag == 'a':
                if 'href' in attrs:
                    value = attrs['href']
                    if len(value) >= 1 and value[0] == '/':
                        self.links.add(value)
            # Detecting forms with actions:
            elif tag == 'form':
                self.current_form_data = attrs.copy()
                # List of form inputs names:
                self.current_form_data['inputs'] = []
                if 'action' not in self.current_form_data.keys():
                    self.current_form_data = None
            # Extracting names of supported form input types:
            elif tag == 'input' and self.current_form_data:
                if 'type' in attrs:
                    if attrs['type'] in input_types:
                        if 'name' in attrs:
                            self.current_form_data['inputs'].append(attrs['name'])
                        elif 'id' in attrs:
                            self.current_form_data['inputs'].append(attrs['id'])

    def handle_endtag(self, tag):
        if self.follow:
            # Saving current from extracted data:
            if tag == 'form' and self.current_form_data:
                form_data = form_fill(self.current_form_data['inputs'], self.database_file)
                if 'method' not in self.current_form_data or self.current_form_data['method'].upper() == 'GET':
                    # Form is GET, making query string:
                    query_string = ""
                    if len(form_data) >= 1:
                        query_string += "?"
                    for i, (key, value) in enumerate(list(form_data.items())):
                        if i != 0:
                            query_string += "&"
                        query_string += "{}={}".format(key, value)
                    self.links.add(self.current_form_data['action'] + query_string)
                elif self.current_form_data['method'].upper() == 'POST':
                    # Form is POST:
                    self.forms.append((self.current_form_data['action'], form_data))
                    self.current_form_data = None


# Natural english language stop words:
stop_words = [
  'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', 'your', 'yours', 'yourself', 'yourselves',
  'he', 'him', 'his', 'himself', 'she', 'her', 'hers', 'herself', 'it', 'its', 'itself', 'they', 'them', 'their',
  'theirs', 'themselves', 'what', 'which', 'who', 'whom', 'this', 'that', 'these', 'those', 'am', 'is', 'are',
  'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'having', 'do', 'does', 'did', 'doing', 'a', 'an',
  'the', 'and', 'but', 'if', 'or', 'because', 'as', 'until', 'while', 'of', 'at', 'by', 'for', 'with', 'about',
  'against', 'between', 'into', 'through', 'during', 'before', 'after', 'above', 'below', 'to', 'from', 'up',
  'down', 'in', 'out', 'on', 'off', 'over', 'under', 'again', 'further', 'then', 'once', 'here', 'there', 'when',
  'where', 'why', 'how', 'all', 'any', 'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor',
  'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 's', 't', 'can', 'will', 'just', 'don', 'should', 'now',
  'dont', 'cant', 'didnt', 'wont', 'shouldnt', 'hadnt', 'hasnt', 'havent']


def tokenize(keywords: str):
    """
    :param keywords: Raw text
    :return: Dict of keys of tokenized words in text and values of their frequency
    """
    # Removing punctuations:
    text = keywords.translate(str.maketrans('', '', punctuation))
    # Splitting the string into a list of words:
    tokens = [token.lower() for token in text.split()]
    # Removing stop words:
    tokens = [token for token in tokens if token not in stop_words]
    stemmer = PorterStemmer()
    # Stemming:
    tokens = [stemmer.stem(token) for token in tokens]
    return dict(Counter(tokens))


def tokenize_html(html_text: str):
    soup = BeautifulSoup(html_text, features="html.parser")
    # Removing script blocks:
    for script in soup.find_all('script'):
        script.decompose()
    # Removing style blocks:
    for style in soup.find_all('style'):
        style.decompose()
    # Removing a blocks:
    for a in soup.find_all('a'):
        a.decompose()
    # Removing HTML:
    return tokenize(soup.get_text())


class Crawler:

    def __init__(self, config: dict):
        self.config = config
        self.logger = Logger(self.config['log_file'])
        self.explored_urls = set()
        self.explored_form_urls = set()
        self.db_conn = sqlite3.connect(self.config['database_file'])
        self.db_conn.execute(''' DROP TABLE IF EXISTS '%s' ''' % self.config['base_url'])
        self.db_conn.execute(''' CREATE TABLE '%s'(Token TEXT, URL TEXT, Freq INTEGER) ''' % self.config['base_url'])
        self.db_conn.commit()
        self.logger.log('Repository for %s (re)created successfully.' % self.config['base_url'])
        self.logger.flush()

    def __text_index(self, url: str, html_txt: str):
        tokens = tokenize_html(html_txt)
        for token, freq in tokens.items():
            self.db_conn.execute(''' INSERT INTO '%s' VALUES('%s', '%s', '%d') ''' %(self.config['base_url'], token, url, freq))
        self.db_conn.commit()
        self.logger.log('Text of page %s%s indexed successfully.' % (self. config['base_url'], url))
        self.logger.flush()

    def crawl(self):
        self.explored_urls.clear()
        self.explored_form_urls.clear()
        self.__crawl('/', 0)

    def __crawl(self, url: str, depth: int):
        if depth > self.config['max_crawl_depth']:
            return
        if url in self.explored_urls:
            return
        sleep(self.config['crawl_sleep_seconds'])
        try:
            request = requests.get(self.config['base_url'] + url)
        except:
            request = None
        # To continue crawling, response status should be OK and content type should be html:
        if request and request.status_code == 200 and 'content-type' in request.headers and request.headers['content-type'].split(';')[0] == 'text/html':
            self.explored_urls.add(url)
            self.logger.log('GET: %s%s' % (self. config['base_url'], url))
            self.logger.flush()
            html_text = request.text
            link_extractor = LinkExtractor(html_text, self.logger, self.config['database_file'])
            links, forms = link_extractor.extract()
            if link_extractor.index:
                self.__text_index(url, html_text)
            for form in forms:
                self.__crawl_form(form[0], form[1], depth + 1)
            for link in links:
                self.__crawl(link, depth + 1)

    def __crawl_form(self, url: str, data: dict, depth: int):
        if depth > self.config['max_crawl_depth']:
            return
        if url in self.explored_form_urls:
            return
        sleep(self.config['crawl_sleep_seconds'])
        try:
            request = requests.post(self.config['base_url'] + url, data)
        except:
            request = None
        # To continue crawling, response status should be OK and content type should be html:
        if request and request.status_code == 200 and 'content-type' in request.headers and request.headers['content-type'].split(';')[0] == 'text/html':
            self.explored_form_urls.add(url)
            self.logger.log("POST: %s %s" % (self. config['base_url'], url))
            self.logger.log("data = " + str(data))
            self.logger.flush()
            html_text = request.text
            link_extractor = LinkExtractor(html_text, self.logger, self.config['database_file'])
            links, forms = link_extractor.extract()
            if link_extractor.index:
                self.__text_index(url, html_text)
            for link in links:
                self.__crawl(link, depth + 1)
            for form in forms:
                self.__crawl_form(form[0], form[1], depth + 1)


def dot_product(d1: dict, d2: dict):
    """
    :return: document distance of vectors d1 and d2
    """
    ans = 0
    for k1 in d1.keys():
        ans += d1[k1] * d2.get(k1, 0)
    return ans


class SearchEngine:

    def __init__(self, config: dict):
        self.config = config
        self.logger = Logger(self.config['log_file'])
        self.db_conn = sqlite3.connect(self.config['database_file'])

    def search(self, base_url: str, keywords: str):
        keywords = tokenize(keywords)
        # dict of urls to dict of keywords to frequencies:
        url_vectors = {}
        # building document vectors in a space with dimensions of keywords:
        for keyword in keywords.keys():
            cursor = self.db_conn.cursor()
            cursor.execute(''' SELECT URL, Freq FROM '%s' WHERE Token='%s' ''' %(base_url, keyword))
            # list of tuple of URL and Freq:
            rows = cursor.fetchall()
            for row in rows:
                if row[0] not in url_vectors:
                    url_vectors[row[0]] = {}
                if keyword not in url_vectors[row[0]]:
                    url_vectors[row[0]][keyword] = 0
                url_vectors[row[0]][keyword] += row[1]
        # list of tuple of document distance of page and keywords and page link:
        urls_with_rank = []
        for url, vector in url_vectors.items():
            urls_with_rank.append((dot_product(keywords, vector), base_url + url))
        urls_with_rank.sort(reverse=True)
        return urls_with_rank

    def search_all(self, keywords: str):
        cursor = self.db_conn.cursor()
        cursor.execute(''' SELECT NAME FROM sqlite_master WHERE type='table' ''')
        # Fetching all page repository table names:
        rows = cursor.fetchall()
        results = []
        for row in rows:
            if row[0] != 'FormFill':
                results.extend(self.search(row[0], keywords))
                self.logger.log('Search through %s completed successfully.' % row[0])
                self.logger.flush()
        # Sort by rank:
        results.sort(reverse=True)
        return results







