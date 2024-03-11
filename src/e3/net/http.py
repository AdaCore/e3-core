from __future__ import annotations

import contextlib
import json
import os
import socket
import tempfile
from collections import deque
from email.message import Message

import requests
import requests.adapters
import requests.exceptions
import urllib3.exceptions
from urllib3.util import Retry

from typing import TYPE_CHECKING

import e3.log
import requests_toolbelt.multipart
from e3.error import E3Error
from e3.fs import rm, mkdir

if TYPE_CHECKING:
    from types import TracebackType
    from typing import Any, Deque, Protocol
    from collections.abc import Callable
    from requests.auth import AuthBase
    from requests.models import Response

    class _Fileobj(Protocol):
        def write(self, __b: bytes) -> object: ...


logger = e3.log.getLogger("net.http")


def get_filename(content_disposition: str) -> str | None:
    """Return a filename from a HTTP Content-Disposition header.

    :param content_disposition: a Content-Disposition header string
    :return: the filename or None
    """
    m = Message()
    m["content-type"] = content_disposition
    filename = m.get_param("filename")
    assert filename is None or isinstance(filename, str)
    return filename


class HTTPError(E3Error):
    def __init__(self, msg: str, status: int | None = None) -> None:
        """Initialize an HTTPError exception.

        :param msg: an error message
        :param status: an optional HTTP status code
        """
        super().__init__(msg)
        self.status = status


class BaseURL:
    """Represent a base url object along with its authentication.

    The root class BaseURL does not use authentication
    """

    def __init__(self, url: str):
        """Initialize a base url object.

        :param url: the base url
        """
        self.url = url

    def get_auth(self) -> tuple[str, str] | AuthBase | None:
        """Return auth requests parameter.

        :return: authentication associated with the url
        """
        return None

    def __str__(self) -> str:
        return self.url


class HTTPSession:
    CHUNK_SIZE = 1024 * 1024
    DEFAULT_TIMEOUT = (60, 60)

    def __init__(self, base_urls: list[str | BaseURL] | None = None):
        """Initialize HTTP session.

        :param base_urls: list of urls used as prefix to subsequent requests.
            Preferred base url is the first one in the list. In case of error
            during a request the next urls are used.
        """
        if base_urls:
            self.base_urls: Deque[BaseURL] | Deque[None] = deque(
                [k if isinstance(k, BaseURL) else BaseURL(k) for k in base_urls]
            )
        else:
            self.base_urls = deque([None])
        self.session = requests.Session()
        self.last_base_url: BaseURL | None = None

    def __enter__(self) -> HTTPSession:
        self.session.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.session.__exit__(exc_type, exc_val, exc_tb)

    def set_max_retries(
        self,
        base_url: str | None = None,
        connect: int | None = None,
        read: int | None = None,
        redirect: int | None = None,
    ) -> None:
        """Retry configuration.

        :param base_url: base url for the HTTPAdapter
        :param connect: how many connection-related errors to retry on
        :param read: how many times to retry on read errors
        :param redirect: how many redirects to perform. Limit this to avoid
            infinite redirect loops.
        """
        if base_url is None:
            base_urls = [str(b) for b in self.base_urls if b is not None]
        else:
            base_urls = [base_url]

        for url in base_urls:
            self.session.mount(
                url,
                requests.adapters.HTTPAdapter(
                    max_retries=Retry(connect=connect, read=read, redirect=redirect)
                ),
            )

    def request(
        self,
        method: str,
        url: str,
        data_streams: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Response:
        """Send a request.

        See requests Session.request function.

        The main difference is that several servers are tried in case
        base_urls have been set.

        For POST requests an additional parameter is supported: data_streams.
        data_streams is a dict associating a string key to either another
        string, a dict, a list or a file descriptor. String value are passed
        without any modifications. lists and dicts are automatically encoded
        in JSON. Finally file objects are streamed during the POST request
        (no complete read is done into memory to fetch file content). When
        using data_streams parameter, data parameter will be ignored and
        headers one modified.
        """
        error_msgs = []
        last_status = None

        for base_url in list(self.base_urls):
            if self.last_base_url != base_url:
                # if base_url is None then it means that self.base_urls is deque([None])
                # in that case last_base_url is always None. The code is confusing and
                # we should remove that complexity by always forcing self.base_urls to
                # be set. ???
                if TYPE_CHECKING:
                    assert base_url is not None
                self.session.auth = base_url.get_auth()
                self.last_base_url = base_url

            logger.debug("try with %s", base_url)

            # Handle data_streams. After some tests it seems that we need to
            # redo an instance of the multipart encoder for each attempt.
            if data_streams is not None:
                data: dict[str, Any] = {}
                for k, v in data_streams.items():
                    if hasattr(v, "seek"):
                        # This is a file. Assume that the key is the filename
                        data[k] = (k, v)
                        v.seek(0)
                    elif isinstance(v, (dict, list)):
                        # Automatically encode to json
                        data[k] = json.dumps(v)
                    else:
                        data[k] = v
                kwargs["data"] = requests_toolbelt.multipart.encoder.MultipartEncoder(
                    data
                )
                header = {"Content-Type": kwargs["data"].content_type}
                if "headers" in kwargs:
                    kwargs["headers"].update(header)
                else:
                    kwargs["headers"] = header

            # Compute final url
            if base_url is not None:
                final_url = f"{base_url}/{url}"
                message_prefix = f"{base_url}: "
            else:
                final_url = url
                message_prefix = ""

            if "timeout" not in kwargs:
                kwargs["timeout"] = self.DEFAULT_TIMEOUT

            try:
                logger.debug("%s %s", method, final_url)
                response = self.session.request(method, final_url, **kwargs)
                if response.status_code != 200:
                    error_msgs.append(f"{message_prefix}{response.text}")
                    last_status = response.status_code
                    response.raise_for_status()
                return response
            except (
                socket.timeout,
                requests.exceptions.RequestException,
                urllib3.exceptions.HTTPError,
            ) as e:
                # got an error with that base url so put it last in our list
                error_msgs.append(f"{message_prefix}{e}")
                problematic_url = self.base_urls.popleft()
                self.base_urls.append(problematic_url)  # type: ignore

        raise HTTPError(
            "got request error (%d):\n%s" % (len(error_msgs), "\n".join(error_msgs)),
            status=last_status,
        )

    def download_file(
        self,
        url: str,
        dest: str | None = None,
        filename: str | None = None,
        fileobj: _Fileobj | None = None,
        validate: Callable[[str], bool] | None = None,
        exception_on_error: bool = False,
        **kwargs: Any,
    ) -> str | None:
        """Download a file.

        :param url: the url to GET
        :param dest: local directory path for the downloaded file. If
            None, a file object must be specified.
        :param filename: the local path whether to store this resource, by
            default use the name provided  in the ``Content-Disposition``
            header.
        :param fileobj: if specified, the downloaded file is written to this
            file object instead of opening a file. The file object must be
            opened in binary mode.
        :param validate: function to call once the download is complete for
            detecting invalid / corrupted download. Takes the local path as
            parameter and returns a boolean. The function is not called
            when a file object is specified.
        :param exception_on_error: if True raises an exception in case download
            fails instead of returning None.
        :param kwargs: additional parameters for the request
        :return: the name of the file, or None if there is an error or a file
            object is passed and the filename could not be deduced from the
            request.
        :raises ValueError: if neither dest nor fileobj is provided
        """
        # When using stream=True, Requests cannot release the connection back
        # to the pool unless all the data is consumed or Response.close called.
        # Force Response.close by wrapping the code with contextlib.closing
        if dest is None and fileobj is None:
            raise ValueError("no destination provided")

        path = None
        try:
            with contextlib.closing(
                self.request(method="GET", url=url, stream=True, **kwargs)
            ) as response:
                content_length = int(response.headers.get("content-length", 0))
                e3.log.debug(response.headers)
                if filename is None:
                    if "content-disposition" in response.headers:
                        filename = get_filename(response.headers["content-disposition"])

                expected_size = content_length // self.CHUNK_SIZE

                chunks = e3.log.progress_bar(
                    response.iter_content(self.CHUNK_SIZE), total=expected_size
                )

                if fileobj is not None:
                    # Write to file object if provided
                    logger.info("downloading %s size=%s", filename, content_length)
                    for chunk in chunks:
                        fileobj.write(chunk)
                    return filename
                else:
                    # Dest can't be None here according to condition at the top
                    assert dest is not None

                    # Fallback to local file otherwise
                    if filename is None:
                        # Generate a temporary name
                        tmpf = tempfile.NamedTemporaryFile(
                            delete=False, dir=dest, prefix="download."
                        )
                        tmpf.close()
                        filename = tmpf.name

                    path = os.path.join(dest, filename)

                    # create dest subdir if they do not exist
                    dest_dir = os.path.dirname(path)
                    if not os.path.exists(dest_dir):
                        mkdir(dest_dir)

                    logger.info("downloading %s size=%s", path, content_length)

                    with open(path, "wb") as fd:
                        for chunk in chunks:
                            fd.write(chunk)

                    if validate is None or validate(path):
                        return path
                    else:
                        rm(path)
        except (requests.exceptions.RequestException, HTTPError) as e:
            # An error (timeout?) occurred while downloading the file
            logger.warning("download failed")
            logger.debug(e)
            if path is not None:
                rm(path)
            if exception_on_error:
                raise
        return None
