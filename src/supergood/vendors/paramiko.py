from uuid import uuid4

import paramiko
import os

from ..constants import REQUEST_ID_KEY

SFTP_SUCCESS_CODE = 200
SFTP_ERROR_CODE = 500
SFTP_GET = 'GET'
SFTP_PUT = 'PUT'

def get_remote_url(hostname, port, remotepath):
    return str('sftp://' + hostname + ':' + str(port) + remotepath)

def safe_get_size(localpath):
    try:
        return os.stat(localpath).st_size
    except FileNotFoundError:
        return None

def safe_get_hostname_and_port(sftp_client):
    try:
        hostname, port = sftp_client.get_channel().get_transport().sock.getpeername()
    except Exception:
        hostname, port = None, None
    return hostname, port

def patch(cache_request, cache_response):
    _original_get = paramiko.sftp_client.SFTPClient.get
    _original_put = paramiko.sftp_client.SFTPClient.put

    def _wrap_get(self, remotepath, localpath, callback=None, prefetch=True, max_concurrent_prefetch_requests=None):
        hostname, port = safe_get_hostname_and_port(self)
        request_id = str(uuid4())
        size = safe_get_size(localpath)
        cache_request(
            request_id,
            get_remote_url(hostname, port, remotepath),
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
            cache_response(request_id, {}, {}, SFTP_ERROR_CODE, repr(e))
            raise e

        cache_response(request_id, {}, {}, SFTP_SUCCESS_CODE, None)

    def _wrap_put(self, localpath, remotepath, callback=None, confirm=True):
        hostname, port = safe_get_hostname_and_port(self)
        request_id = str(uuid4())
        cache_request(request_id, get_remote_url(hostname, port, remotepath), SFTP_PUT, {}, {})
        response_body = {
            "local_path": localpath,
            "remote_path": remotepath,
        }
        try:
            sftp_attrs = _original_put(self, localpath, remotepath, callback, confirm)
            response_body['size'] = sftp_attrs.st_size
        except Exception as e:
            # Log error in Supergood
            cache_response(request_id, response_body, {}, SFTP_ERROR_CODE, repr(e))
            raise e

        cache_response(request_id, response_body, {}, SFTP_SUCCESS_CODE, repr(sftp_attrs))
        return sftp_attrs

    paramiko.sftp_client.SFTPClient.get = _wrap_get
    paramiko.sftp_client.SFTPClient.put = _wrap_put
