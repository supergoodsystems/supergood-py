import signal

SIGNALS = [
    signal.SIGTERM,
    signal.SIGINT,
]
REQUEST_ID_KEY = "_supergood_request_id"
GZIP_START_BYTES = b"\x1f\x8b"
DEFAULT_SUPERGOOD_BYTE_LIMIT = 500000
DEFAULT_SUPERGOOD_BASE_URL = "https://api.supergood.ai/"
DEFAULT_SUPERGOOD_TELEMETRY_URL = "https://telemetry.supergood.ai"
DEFAULT_SUPERGOOD_CONFIG = {
    "flushInterval": 1000,
    "configInterval": 10000,
    "eventSinkEndpoint": "/events",
    "errorSinkEndpoint": "/errors",
    "remoteConfigEndpoint": "/config",
    "telemetryPostEndpoint": "/telemetry",
    "ignoredDomains": [],
    "forceRedactAll": False,  # redact all payloads, ignores other flags when set
    "logRequestHeaders": True,  # more fine-grained redaction for each of the request|response body|headers
    "logRequestBody": True,
    "logResponseHeaders": True,
    "logResponseBody": True,
    "ignoreRedaction": False,  # ignores redaction. Lowest priority flag
    "useRemoteConfig": True,
    "runThreads": True,
    "redactByDefault": False,
}

ERRORS = {
    "CACHING_RESPONSE": "Error Caching Response",
    "CACHING_REQUEST": "Error Caching Request",
    "DUMPING_DATA_TO_DISK": "Error Dumping Data to Disk",
    "POSTING_EVENTS": "Error Posting Events",
    "POSTING_ERRORS": "Error Posting Errors",
    "FETCHING_CONFIG": "Error Fetching Config",
    "WRITING_TO_DISK": "Error writing to disk",
    "TEST_ERROR": "Test Error for Testing Purposes",
    "UNINITIALIZED": "Client not properly initialized",
    "UNAUTHORIZED": "Unauthorized: Invalid Client ID or Secret. Exiting.",
    "NO_CLIENT_ID": "No Client ID Provided, set SUPERGOOD_CLIENT_ID or pass it as an argument",
    "NO_CLIENT_SECRET": "No Client Secret Provided, set SUPERGOOD_CLIENT_SECRET or pass it as an argument",
    "UNKNOWN": "Client received unexpected value",
    "REDACTION": "Client failed to redact sensitive keys",
    "LOCK_STATE": "Client lock state ambiguous",
    "POSTING_TELEMETRY": "Error posting telemetry",
}
