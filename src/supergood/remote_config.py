import json
import re
from dataclasses import dataclass
from typing import Dict, List
from urllib.parse import urlparse

from tldextract import extract


@dataclass
class SensitiveKey:
    """
    Key-level config
    key_path: path of key to action on
    action: 'REDACT' (redacts value) ('HASH' and 'IGNORE' not supported for now)
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
    sensitive_keys: List[SensitiveKey]


def get_endpoint_test_val(
    location,
    url=None,
    request_body=None,
    request_headers=None,
):
    """
    Uses the location to find the correct value to check endpoint regex against
    """
    if location == "path":
        return urlparse(url).path
    elif location == "url":
        return url
    elif location == "domain":
        return extract(url).domain
    elif location == "subdomain":
        return extract(url).subdomain
    elif location == "requestHeaders":
        return json.dumps(request_headers)
    elif location == "requestBody":
        return json.dumps(request_body)
    else:
        return ""


def get_endpoint_from_config(
    remote_config,
    url=None,
    request_body=None,
    request_headers=None,
):
    url_extract = extract(url)
    search = url_extract.fqdn or url_extract.domain
    vendor_domain = next((dom for dom in remote_config if dom in search), None)
    if vendor_domain:
        return next(
            (
                ep
                for ep in remote_config[vendor_domain]
                if ep.regex.search(
                    get_endpoint_test_val(
                        location=ep.location,
                        url=url,
                        request_body=request_body,
                        request_headers=request_headers,
                    )
                )
            ),
            None,
        )


def parse_remote_config_json(
    config: List[Dict],
) -> Dict[str, List[EndpointConfiguration]]:
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
