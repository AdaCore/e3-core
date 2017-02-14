from __future__ import absolute_import, division, print_function

import logging
import os
import threading
import time

from e3.net.http import HTTPSession

try:
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
except ImportError:
    from http.server import BaseHTTPRequestHandler, HTTPServer


class RetryHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if hasattr(self.server, 'tries'):
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'OK')
            self.wfile.close()
            self.server.tries += 1
        else:
            self.server.tries = 1


class RetryAbortHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if hasattr(self.server, 'tries'):
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.send_header('Content-Lenght', '4500')
            self.end_headers()
            self.wfile.write(b'OK')
            time.sleep(1.0)
        else:
            self.server.tries = 1


class ContentDispoHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.send_header('content-disposition',
                         'attachment;filename="dummy.txt"')
        self.end_headers()
        self.wfile.write(b'Dummy!')
        self.wfile.close()


class ServerErrorHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not hasattr(self.server, 'calls'):
            self.server.calls = 1
        else:
            self.server.calls += 1
        self.send_response(500)
        self.end_headers()
        self.wfile.close()


def run_server(handler, func):
    server = HTTPServer(('localhost', 0), handler)
    try:
        thread = threading.Thread(target=server.serve_forever)
        thread.daemon = True
        thread.start()
        base_url = 'http://%s:%s/' % server.server_address
        func(server, base_url)
    finally:
        server.shutdown()


class TestHTTP(object):

    def test_session(self):
        """Create a session in a context."""
        with HTTPSession():
            pass

    def test_session_download(self):
        with HTTPSession() as session:
            result = session.download_file('http://google.com', dest='.')
            assert result is not None

    def test_retry(self):
        def func(server, base_url):
            with HTTPSession() as session:
                session.set_max_retries(base_url, connect=5)
                result = session.download_file(base_url + 'dummy', dest='.')
                with open(result, 'rb') as fd:
                    content = fd.read()
                assert content == b'OK'
                assert server.tries == 2

        run_server(RetryHandler, func)

    def test_content_dispo(self):
        def func(server, base_url):
            with HTTPSession() as session:
                result = session.download_file(base_url + 'dummy', dest='.')
                with open(result, 'rb') as fd:
                    content = fd.read()
                assert content == b'Dummy!'
                assert os.path.basename(result) == 'dummy.txt'

        run_server(ContentDispoHandler, func)

    def test_content_validation(self):
        def validate(path):
            return False

        def func(server, base_url):
            with HTTPSession() as session:
                result = session.download_file(base_url + 'dummy', dest='.',
                                               validate=validate)
                assert result is None

        run_server(ContentDispoHandler, func)

    def test_error(self):
        def func(server, base_url):
            with HTTPSession() as session:
                result = session.download_file(base_url + 'dummy', dest='.')
                assert result is None

        run_server(ServerErrorHandler, func)

    def test_fallback(self):
        def func(server, base_url):
            def inner_func(server2, base_url2):
                logging.info('servers: %s, %s' % (base_url, base_url2))
                with HTTPSession(base_urls=[base_url, base_url2]) as session:
                    session.set_max_retries(connect=4)
                    result = session.download_file(base_url + 'dummy',
                                                   dest='.')
                    assert result is not None
                    assert server.calls == 1
                    assert server2.tries == 2
            run_server(RetryHandler, inner_func)

        run_server(ServerErrorHandler, func)

    def test_content_abort(self):
        def func(server, base_url):
            def inner_func(server2, base_url2):
                logging.info('servers: %s, %s' % (base_url, base_url2))
                with HTTPSession(base_urls=[base_url, base_url2]) as session:
                    session.DEFAULT_TIMEOUT = (10.0, 0.2)
                    session.set_max_retries(connect=4)
                    result = session.download_file(base_url + 'dummy',
                                                   dest='.')
                    assert result is None
                    assert server.calls == 1
                    assert server2.tries == 1

            run_server(RetryAbortHandler, inner_func)

        run_server(ServerErrorHandler, func)
