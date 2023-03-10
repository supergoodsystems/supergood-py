def get_config(flush_interval=30000, keys_to_hash=[], ignored_domains=[]):
    return {
                'flushInterval': flush_interval,
                'eventSinkEndpoint': 'https://dashboard.supergood.ai/api/events',
                'errorSinkEndpoint': 'https://dashboard.supergood.ai/api/errors',
                'keysToHash': keys_to_hash,
                'ignoredDomains': ignored_domains
            }
