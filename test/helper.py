def get_config(httpserver, flush_interval=30000, keys_to_hash=[], ignored_domains=[]):
    return {
                'flushInterval': flush_interval,
                'eventSinkEndpoint': httpserver.url_for('/api/events'),
                'errorSinkEndpoint': httpserver.url_for('/api/errors'),
                'keysToHash': keys_to_hash,
                'ignoredDomains': ignored_domains
            }
