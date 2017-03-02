from __future__ import absolute_import, division, print_function

import cgi
import contextlib
import json
import os
import socket
import tempfile
from collections import deque

import e3.log
import requests
import requests.adapters
import requests.exceptions
import requests.packages.urllib3.exceptions
import requests_toolbelt.multipart
from e3.error import E3Error
from e3.fs import rm
from requests.packages.urllib3.util import Retry

logger = e3.log.getLogger('net.http')


def get_filename(content_disposition):
    """Return a filename from a HTTP Content-Disposition header.

    :param content_disposition: a Content-Disposition header string
    :type content_disposition: str
    :return: the filename or None
    :rtype: str
    """
    _, value = cgi.parse_header(content_disposition)
    return value.get('filename')


class HTTPError(E3Error):
    pass


class BaseURL(object):
    """Represent a base url object along with its authentication.

    The root class BaseURL does not use authentication
    """

    def __init__(self, url):
        """Initialize a base url object.

        :param url: the base url
        :type url: str
        """
        self.url = url

    def get_auth(self):
        """Return auth requests parameter.

        :return: authentication associated with the url
        :rtype: (str, str) | requests.auth.AuthBase | None
        """
        return None

    def __str__(self):
        return self.url


class HTTPSession(object):

    CHUNK_SIZE = 1024 * 1024
    DEFAULT_TIMEOUT = (60, 60)

    def __init__(self, base_urls=None):
        """Initialize HTTP session.

        :param base_urls: list of urls used as prefix to subsequent requests.
            Preferred base url is the first one in the list. In case of error
            during a request the next urls are used.
        :type base_urls: list[str] | list[BaseUrl] | None
        """
        if base_urls:
            self.base_urls = deque([k if isinstance(k, BaseURL) else BaseURL(k)
                                    for k in base_urls])
        else:
            self.base_urls = deque([None])
        self.session = requests.Session()
        self.last_base_url = None

    def __enter__(self):
        self.session.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.__exit__(exc_type, exc_val, exc_tb)

    def set_max_retries(self,
                        base_url=None,
                        connect=None,
                        read=None,
                        redirect=None):
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
        if base_url is None:
            base_urls = self.base_urls
        else:
            base_urls = [base_url]

        for url in base_urls:
            self.session.mount(str(url), requests.adapters.HTTPAdapter(
                max_retries=Retry(
                    connect=connect, read=read, redirect=redirect)))

    def request(self, method, url, **kwargs):
        """Send a request.

        See requests Session.request function.

        The main difference is that several servers are tried in case
        base_urls have been set.

        For POST requests an additional parameter is supported: data_streams.
        data_streams is a dict associating a string key to either another
        string, a dict, a list or a file descriptor. String value are passed
        without any modifications. Lists and dicts are automatically encoded
        in JSON. Finally file objects are streamed during the POST request
        (no complete read is done into memory to fetch file content). When
        using data_streams parameter, data parameter will be ignored and
        headers one modified.
        """
        error_msgs = []
        data_streams = None

        # Keep data_streams apart as it is not an argument to request
        if 'data_streams' in kwargs:
            data_streams = kwargs['data_streams']
            del kwargs['data_streams']

        for base_url in list(self.base_urls):
            if self.last_base_url != base_url:
                self.session.auth = base_url.get_auth()
                self.last_base_url = base_url

            logger.debug('try with %s', base_url)

            # Handle data_streams. After some tests it seems that we need to
            # redo an instance of the multipart encoder for each attempt.
            if data_streams is not None:
                data = {}
                for k, v in data_streams.iteritems():
                    if hasattr(v, 'seek'):
                        # This is a file. Assume that the key is the filename
                        data[k] = (k, v)
                        v.seek(0)
                    elif isinstance(v, dict) or isinstance(v, list):
                        # Automatically encode to json
                        data[k] = json.dumps(v)
                    else:
                        data[k] = v
                kwargs['data'] = \
                    requests_toolbelt.multipart.encoder.MultipartEncoder(data)
                header = {'Content-Type': kwargs['data'].content_type}
                if 'headers' in kwargs:
                    kwargs['headers'].update(header)
                else:
                    kwargs['headers'] = header

            # Compute final url
            if base_url is not None:
                final_url = '%s/%s' % (base_url, url)
                message_prefix = '%s: ' % base_url
            else:
                final_url = url
                message_prefix = ''

            if 'timeout' not in kwargs:
                kwargs['timeout'] = self.DEFAULT_TIMEOUT

            try:
                logger.debug('%s %s', method, final_url)
                response = self.session.request(method, final_url, **kwargs)
                if response.status_code != 200:
                    error_msgs.append('%s%s' % (message_prefix, response.text))
                    response.raise_for_status()
                return response
            except (socket.timeout, requests.exceptions.RequestException,
                    requests.packages.urllib3.exceptions.HTTPError) as e:
                # got an error with that base url so put it last in our list
                error_msgs.append('%s%s' % (message_prefix, e))
                problematic_url = self.base_urls.popleft()
                self.base_urls.append(problematic_url)

        raise HTTPError('got request error (%d):\n%s' %
                        (len(error_msgs), '\n'.join(error_msgs)))

    def download_file(self, url, dest, filename=None, validate=None):
        """Download a file.

        :param url: the url to GET
        :type url: str
        :param dest: local directory path for the downloaded file
        :type dest: str
        :param filename: the local path whether to store this resource, by
            default use the name provided  in the ``Content-Disposition``
            header.
        :param validate: function to call once the download is complete for
            detecting invalid / corrupted download. Takes the local path as
            parameter and returns a boolean.
        :type validate: (str) -> bool
        :return: the name of the file or None if there is an error
        :rtype: str
        """
        # When using stream=True, Requests cannot release the connection back
        # to the pool unless all the data is consumed or Response.close called.
        # Force Response.close by wrapping the code with contextlib.closing

        path = None
        try:
            with contextlib.closing(
                    self.request(method='GET',
                                 url=url,
                                 stream=True)) as response:
                content_length = int(response.headers.get(
                    'content-length', 0))
                e3.log.debug(response.headers)
                if filename is None:
                    if 'content-disposition' in response.headers:
                        filename = get_filename(
                            response.headers['content-disposition'])
                    if filename is None:
                        # Generate a temporary name
                        tmpf = tempfile.NamedTemporaryFile(
                            delete=False,
                            dir=dest,
                            prefix='download.')
                        tmpf.close()
                        filename = tmpf.name

                path = os.path.join(dest, filename)
                logger.info('downloading %s size=%s', path, content_length)

                expected_size = content_length // self.CHUNK_SIZE
                with open(path, 'wb') as fd:
                    for chunk in e3.log.progress_bar(
                            response.iter_content(self.CHUNK_SIZE),
                            total=expected_size):
                        fd.write(chunk)
                if validate is None or validate(path):
                    return path
                else:
                    rm(path)
        except (requests.exceptions.RequestException, HTTPError) as e:
            # An error (timeout?) occurred while downloading the file
            logger.warning('download failed')
            logger.debug(e)
            if path is not None:
                rm(path)
            return None
