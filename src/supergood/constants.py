import signal

SIGNALS = [
    signal.SIGTERM,
    signal.SIGINT,
]
REQUEST_ID_KEY = '_supergood_request_id'
GZIP_START_BYTES = b'\x1f\x8b'
DEFAULT_SUPERGOOD_BYTE_LIMIT = 500000
DEFAULT_SUPERGOOD_CONFIG_URL = 'https://dashboard.supergood.ai/api/config/'
DEFAULT_SUPERGOOD_BASE_URL = 'https://dashboard.supergood.ai/'
DEFAULT_SUPERGOOD_CONFIG = {
    'flushInterval': 1000,
    'eventSinkEndpoint': '/api/events',
    'errorSinkEndpoint': '/api/errors',
    'keysToHash': ['request.body', 'response.body'],
    'ignoredDomains': []
}

ERRORS = {
    "CACHING_RESPONSE": 'Error Caching Response',
    "CACHING_REQUEST": 'Error Caching Request',
    "DUMPING_DATA_TO_DISK": 'Error Dumping Data to Disk',
    "POSTING_EVENTS": 'Error Posting Events',
    "POSTING_ERRORS": 'Error Posting Errors',
    "FETCHING_CONFIG": 'Error Fetching Config',
    "WRITING_TO_DISK": 'Error writing to disk',
    "TEST_ERROR": 'Test Error for Testing Purposes',
    "UNAUTHORIZED": 'Unauthorized: Invalid Client ID or Secret. Exiting.',
    "NO_CLIENT_ID":
    'No Client ID Provided, set SUPERGOOD_CLIENT_ID or pass it as an argument',
    "NO_CLIENT_SECRET":
    'No Client Secret Provided, set SUPERGOOD_CLIENT_SECRET or pass it as an argument'
}
