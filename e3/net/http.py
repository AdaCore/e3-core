from __future__ import absolute_import

import contextlib
import os
import socket
import requests
import requests.adapters
import requests.packages.urllib3.exceptions
from requests.packages.urllib3.util import Retry
import requests.exceptions

import e3.log

logger = e3.log.getLogger('net.http')


class HTTPSession(object):

    CHUNK_SIZE = 1024 * 1024
    DEFAULT_TIMEOUT = (60, 60)

    def __enter__(self):
        self.session = requests.Session()
        self.session.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.__exit__(exc_type, exc_val, exc_tb)

    def set_max_retries(self, base_url,
                        connect=None, read=None, redirect=None):
        """Retry configuration.

        :param base_url: base url for the HTTPAdapter
        :type base_url: str
        :param connect: how many connection-related errors to retry on
        :type connect: int | None
        :param read: how many times to retry on read errors
        :type read: int | None
        :param redirect: how many redirects to perform. Limit this to avoid
            infinite redirect loops.
        :type redirect: int | None
        """
        self.session.mount(base_url, requests.adapters.HTTPAdapter(
            max_retries=Retry(
                connect=connect, read=read, redirect=redirect)))

    def download_file(self, url, path, validate=None):
        """Download a file.

        :param url: the url to GET
        :type url: str
        :param path: local path for the downloaded file
        :type path: str
        :param validate: function to call once the download is complete for
            detecting invalid / corrupted download. Takes the local path as
            parameter and returns a boolean.
        :type validate: (str) -> bool
        :return: True if download succeeed, False otherwise
        :rtype: bool
        """
        logger.info('downloading %s from %s', path, url)
        # When using stream=True, Requests cannot release the connection back
        # to the pool unless all the data is consumed or Response.close called.
        # Force Response.close by wrapping the code with contextlib.closing
        with contextlib.closing(
                self.session.get(url, stream=True,
                                 timeout=self.DEFAULT_TIMEOUT)) as response:
            try:
                content_length = int(response.headers.get('content-length'))
                expected_size = content_length / self.CHUNK_SIZE
                with open(path, 'wb') as fd:
                    for chunk in e3.log.progress_bar(
                            response.iter_content(self.CHUNK_SIZE),
                            expected_size=expected_size):
                        fd.write(chunk)
                return True
            except (socket.timeout, requests.exceptions.RequestException,
                    requests.packages.urllib3.exceptions.HTTPError) as e:
                # An error (timeout?) occurred while downloading the file
                logger.debug('error when downloading %s content from %s',
                             os.path.basename(path), url)
                logger.debug(e)
                return False
