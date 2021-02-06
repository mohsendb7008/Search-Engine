from classes import *

config = {
    "database_file": "data.db",
    "log_file": "search_engine_log.txt"
}

if __name__ == '__main__':
    search_engine = SearchEngine(config)
    while True:
        keywords = input('Keywords= ')
        search_engine.logger.log('Searching for "%s"...' % keywords)
        results = search_engine.search_all(keywords)
        for result in results:
            search_engine.logger.log(str(result[0]) + " " + result[1])
        search_engine.logger.flush()
