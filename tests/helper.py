def get_config(flush_interval=30000, included_keys=[], ignored_domains=[]):
    return {
                'flushInterval': flush_interval,
                'eventSinkEndpoint': 'https://dashboard.supergood.ai/api/events',
                'errorSinkEndpoint': 'https://dashboard.supergood.ai/api/errors',
                'includedKeys': included_keys,
                'ignoredDomains': ignored_domains
            }
