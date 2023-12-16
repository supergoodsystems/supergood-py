def get_config(
    flush_interval=30000,
    ignored_domains=[],
    ignore_redaction=False,
    config_interval=10000,
):
    return {
        "flushInterval": flush_interval,
        "configInterval": config_interval,
        "eventSinkEndpoint": "https://api.supergood.ai/events",
        "errorSinkEndpoint": "https://api.supergood.ai/errors",
        "ignoredDomains": ignored_domains,
        "ignoreRedaction": ignore_redaction,
    }


def build_key(key_path, key_action="REDACT"):
    return {"keyPath": key_path, "action": key_action}


def get_remote_config(action="Allow", keys=[]):
    built_keys = list(map(lambda tup: build_key(tup[0], tup[1]), keys))
    return [
        {
            "domain": "localhost",
            "id": "vendor-id",
            "endpoints": [
                {
                    "id": "endpoint-id",
                    "matchingRegex": {"location": "path", "regex": "200"},
                    "endpointConfiguration": {
                        "action": action,
                        "sensitiveKeys": built_keys,
                    },
                }
            ],
        }
    ]
