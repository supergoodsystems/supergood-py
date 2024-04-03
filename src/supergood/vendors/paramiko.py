from uuid import uuid4

import paramiko
import os

from ..constants import REQUEST_ID_KEY

SFTP_SUCCESS_CODE = 200
SFTP_ERROR_CODE = 500
SFTP_GET = 'GET'
SFTP_PUT = 'PUT'

def patch(cache_request, cache_response):
    _original_get = paramiko.SFTPFile.get
    _original_put = paramiko.SFTPFile.put

    def _wrap_get(self, remotepath, localpath, callback=None, prefetch=True, max_concurrent_prefetch_requests=None):
        request_id = str(uuid4())
        size = os.stat(localpath).st_size
        cache_request(
            request_id,
            str(remotepath),
            SFTP_GET,
            {
                "remote_path": remotepath,
                "local_path": localpath,
                "size": size
            },
            {}
        )
        try:
            _original_get(self, remotepath, localpath, callback, prefetch, max_concurrent_prefetch_requests)
        except Exception as e:
            # Log error in Supergood
            cache_response(request_id, None, None, SFTP_ERROR_CODE, repr(e))
            raise e
        cache_response(request_id, None, None, SFTP_SUCCESS_CODE, None)

    def _wrap_put(self, localpath, remotepath, callback=None, confirm=True):
        request_id = str(uuid4())
        cache_request(request_id, str(remotepath), SFTP_PUT, None, None)
        try:
            sftp_attrs = _original_put(self, localpath, remotepath, callback, confirm)
        except Exception as e:
            # Log error in Supergood
            cache_response(request_id, None, None, SFTP_ERROR_CODE, repr(e))
            raise e
        cache_response(request_id, None, None, SFTP_SUCCESS_CODE, repr(sftp_attrs))
        return sftp_attrs

    paramiko.SFTPFile.get = _wrap_get
    paramiko.SFTPFile.put = _wrap_put
