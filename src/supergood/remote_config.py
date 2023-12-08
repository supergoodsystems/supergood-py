import re
from dataclasses import dataclass


@dataclass
class SensitiveKey:
    """
    Key-level config
    key_path: path of key to action on
    action: 'HASH' (md5 hashes value) 'IGNORE' (removes key) 'REDACT' (redacts value)
    """

    key_path: str
    action: str


@dataclass
class EndpointConfiguration:
    """
    API-level config
    regex: Regex used to uniquely identify the endpoint
    location: Where to find the value to test the regex against
    action: 'Allow' (no-ops), 'Ignore' (does not cache)
    sensitive_keys: Keys to redact from the request and response
    """

    regex: re.Pattern
    location: str
    action: str
    sensitive_keys: list[SensitiveKey]


def parse_remote_config_json(
    config: list[dict],
) -> dict[str, list[EndpointConfiguration]]:
    remote_config = {}
    for entry in config:
        endpoints = []
        for endpoint in entry.get("endpoints"):
            matchingRegex = endpoint.get("matchingRegex")
            endpointConfiguration = endpoint.get("endpointConfiguration")
            if not endpointConfiguration:
                # Assume 'Allow' and no sensitive keys when conf is empty
                action = "Allow"
                sensitive_keys = []
            else:
                action = endpointConfiguration.get("action")
                sensitive_keys = list(
                    map(
                        lambda key: SensitiveKey(key.get("keyPath"), key.get("action")),
                        endpointConfiguration.get("sensitiveKeys"),
                    )
                )

            regex = re.compile(matchingRegex.get("regex"))
            endpoints.append(
                EndpointConfiguration(
                    regex,
                    matchingRegex.get("location"),
                    action,
                    sensitive_keys,
                )
            )
        remote_config[entry.get("domain")] = endpoints

    return remote_config
