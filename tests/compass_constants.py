import uuid

URL = "/".join(
    [
        "https://www.compass.com",
        "homes-for-sale",
        "_map",
        "mapview=60.3483604,-59.3757527,-21.3309463,-130.3913777",
        "status=active",
        "listing-type=exclusive/",
    ]
)
HEADERS = {
    "authority": "www.compass.com",
    "accept": "*/*",
    "accept-language": "en-US;q=0.5",
    "content-type": "application/json",
    "referer": "https://www.compass.com/",
    "user-agent": " ".join(
        [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "AppleWebKit/537.36 (KHTML, like Gecko)",
            "Chrome/103.0.5060.53 Safari/537.36",
        ]
    ),
    "accept-encoding": "gzip, deflate, br",
}
PAYLOAD = {
    "searchResultId": str(uuid.uuid4()),
    "rawLolSearchQuery": {
        "listingTypes": [2],
        "nePoint": {"latitude": 74.2206068, "longitude": -59.3757527},
        "swPoint": {"latitude": -21.8320695, "longitude": -130.3913777},
        "saleStatuses": [9],
        "compassListingTypes": [2],
        "num": 41,
        "sortOrder": 115,
        "locationIds": [],
        "facetFieldNames": [
            "contributingDatasetList",
            "compassListingTypes",
            "comingSoon",
        ],
    },
    "width": 809,
    "height": 1116,
    "viewportFrom": "map",
    "viewport": {
        "northeast": {"lat": 60.3483604, "lng": -59.3757527},
        "southwest": {"lat": -21.3309463, "lng": -130.3913777},
    },
    "purpose": "search",
}
