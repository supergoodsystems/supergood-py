def get_config(flush_interval=30000, included_keys=[], ignored_domains=[], ignore_redaction=False):
    return {
                'flushInterval': flush_interval,
                'eventSinkEndpoint': 'https://api.supergood.ai/events',
                'errorSinkEndpoint': 'https://api.supergood.ai/errors',
                'includedKeys': included_keys,
                'ignoredDomains': ignored_domains,
                'ignoreRedaction': ignore_redaction
            }
