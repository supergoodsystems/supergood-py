import os
from logging import INFO, basicConfig, getLogger

from dotenv import load_dotenv

load_dotenv()
basicConfig(level=INFO)


class Logger:
    def __init__(self, logger_name, config, api):
        self.config = config
        self.log = getLogger(logger_name)
        if os.getenv("SUPERGOOD_LOG_LEVEL") == "debug":
            self.log.setLevel(10)
        self.api = api

    def error(self, error, exc_info, data={}):
        self.log.error(error)
        self.log.error(exc_info)
        self.api.post_errors(data, exc_info, error)

    def info(self, info):
        self.log.info(info)

    def warning(self, warning):
        self.log.warning(warning)

    def debug(self, debug):
        self.log.debug(debug)
