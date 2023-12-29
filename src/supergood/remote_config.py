import json
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple, Union
from urllib.parse import urlparse

import tldextract


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

    endpoint_id: str
    regex: re.Pattern
    location: str
    action: str
    sensitive_keys: List[SensitiveKey]


@dataclass
class VendorConfiguration:
    """
    Vendor-level config
    id: vendor UUID
    endpoints: List of known endpoints
    """

    domain: str
    vendor_id: str
    endpoints: Dict[str, EndpointConfiguration]


def get_endpoint_test_val(
    location,
    url=None,
    request_body=None,
    request_headers=None,
):
    """
    Uses the location to find the correct value to check endpoint regex against
    """
    # Only uses provided TLD cache. Doesnt make call for updates
    extract = tldextract.TLDExtract(suffix_list_urls=())
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


def get_vendor_endpoint_from_config(
    remote_config,
    url=None,
    request_body=None,
    request_headers=None,
) -> Tuple[Union[None, VendorConfiguration], Union[None, EndpointConfiguration]]:
    """
    Using the url, request_body, and request_headers
    matches to the vendors/endpoints in remote_config
    and returns a tuple of (VendorConfiguration, EndpointConfiguration)
    if it finds a match, otherwise (None, None)
    """
    extract = tldextract.TLDExtract(suffix_list_urls=())
    url_extract = extract(url)
    search = url_extract.fqdn or url_extract.domain
    vendor_config = next(
        (vcfg for vcfg in remote_config.values() if vcfg.domain in search), None
    )
    if vendor_config:
        return vendor_config, next(
            (
                ep
                for ep in vendor_config.endpoints.values()
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
    else:
        return (None, None)


def parse_remote_config_json(
    config: List[Dict],
) -> Dict[str, VendorConfiguration]:
    remote_config = {}
    for entry in config:
        vendor_id = entry.get("id")
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
                    endpoint.get("id"),
                    regex,
                    matchingRegex.get("location"),
                    action,
                    sensitive_keys,
                )
            )
        vendor_config = VendorConfiguration(
            vendor_id=vendor_id,
            domain=entry.get("domain"),
            endpoints={ep.endpoint_id: ep for ep in endpoints},
        )
        remote_config[vendor_id] = vendor_config

    return remote_config
