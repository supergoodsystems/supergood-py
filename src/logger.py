import os
from dotenv import load_dotenv
from logging import getLogger, basicConfig, INFO

load_dotenv()
basicConfig(level=INFO)

class Logger:
    def __init__(self, logger_name, config, api):
        self.config = config
        self.log = getLogger(logger_name)
        if(os.getenv('SUPERGOOD_LOG_LEVEL') == 'debug'):
            self.log.setLevel(10)
        self.api = api

    def error(self, data, error, message):
        self.log.error(error)
        self.api.post_errors(data, error, message)

    def info(self, info):
        self.log.info(info, self.config)

    def warning(self, warning):
        self.log.warning(warning, self.config)

    def debug(self, debug):
        self.log.debug(debug, self.config)

