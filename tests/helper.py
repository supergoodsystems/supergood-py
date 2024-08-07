def get_config(
    flush_interval=30000,
    ignored_domains=[],
    ignore_redaction=False,
    config_interval=10000,
    log_request_body=True,
    log_request_headers=True,
    log_response_body=True,
    log_response_headers=True,
    force_redact_all=False,
    redact_by_default=False,
):
    return {
        "flushInterval": flush_interval,
        "configInterval": config_interval,
        "eventSinkEndpoint": "https://api.supergood.ai/events",
        "errorSinkEndpoint": "https://api.supergood.ai/errors",
        "ignoredDomains": ignored_domains,
        "ignoreRedaction": ignore_redaction,
        "logRequestHeaders": log_request_headers,
        "logRequestBody": log_request_body,
        "logResponseHeaders": log_response_headers,
        "logResponseBody": log_response_body,
        "forceRedactAll": force_redact_all,
        "redactByDefault": redact_by_default,
    }


def build_key(key_path, key_action="REDACT"):
    return {"keyPath": key_path, "action": key_action}


def get_remote_config(
    action="Allow", keys=[], location="path", regex="200", method="GET"
):
    built_keys = list(map(lambda tup: build_key(tup[0], tup[1]), keys))
    return [
        {
            "domain": "localhost",
            "id": "vendor-id",
            "endpoints": [
                {
                    "id": "endpoint-id",
                    "method": method,
                    "matchingRegex": {"location": location, "regex": regex},
                    "endpointConfiguration": {
                        "action": action,
                        "sensitiveKeys": built_keys,
                    },
                }
            ],
        }
    ]
