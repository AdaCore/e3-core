import cgi
import logging
import os
import threading
import time

import requests_toolbelt.multipart
from e3.net.http import HTTPSession

try:
    from http.server import BaseHTTPRequestHandler, HTTPServer
except ImportError:
    from http.server import BaseHTTPRequestHandler, HTTPServer


class RetryHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if hasattr(self.server, "tries"):
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"OK")
            self.wfile.close()
            self.server.tries += 1
        else:
            self.server.tries = 1


class RetryAbortHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if hasattr(self.server, "tries"):
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.send_header("Content-Lenght", "4500")
            self.end_headers()
            self.wfile.write(b"OK")
            time.sleep(1.0)
        else:
            self.server.tries = 1


class ContentDispoHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.send_header("content-disposition", 'attachment;filename="dummy.txt"')
        self.end_headers()
        self.wfile.write(b"Dummy!")
        self.wfile.close()


class ServerErrorHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not hasattr(self.server, "calls"):
            self.server.calls = 1
        else:
            self.server.calls += 1
        self.send_response(500)
        self.end_headers()
        self.wfile.close()

    def do_POST(self):
        self.send_response(500)
        self.end_headers()


class MultiPartPostHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if "Content-Type" not in self.headers:
            self.send_response(200)
            self.end_headers()
            return

        content = self.rfile.read(int(self.headers["Content-Length"]))
        decoder = requests_toolbelt.multipart.MultipartDecoder(
            content, self.headers["Content-Type"]
        )

        logging.debug("POST received")
        self.server.test_payloads = {}
        for part in decoder.parts:
            logging.debug(list(part.headers.keys()))
            # With python 3.x requests_toolbelt returns bytes
            _, value = cgi.parse_header(
                part.headers[b"Content-Disposition"].decode("utf-8")
            )
            self.server.test_payloads[value["name"]] = part.text

        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"OK")
        logging.debug("POST finish")


def run_server(handler, func):
    server = HTTPServer(("localhost", 0), handler)
    try:
        thread = threading.Thread(target=server.serve_forever)
        thread.daemon = True
        thread.start()
        base_url = "http://%s:%s/" % server.server_address
        func(server, base_url)
    finally:
        server.shutdown()
        server.server_close()


class TestHTTP:
    def test_session(self):
        """Create a session in a context."""
        with HTTPSession():
            pass

    def test_retry(self, socket_enabled):
        def func(server, base_url):
            with HTTPSession() as session:
                session.set_max_retries(base_url, connect=5)
                result = session.download_file(base_url + "dummy", dest=".")
                with open(result, "rb") as fd:
                    content = fd.read()
                assert content == b"OK"
                assert server.tries == 2

        run_server(RetryHandler, func)

    def test_content_dispo(self, socket_enabled):
        def func(server, base_url):
            with HTTPSession() as session:
                result = session.download_file(base_url + "dummy", dest=".")
                with open(result, "rb") as fd:
                    content = fd.read()
                assert content == b"Dummy!"
                assert os.path.basename(result) == "dummy.txt"

        run_server(ContentDispoHandler, func)

    def test_content_validation(self, socket_enabled):
        def validate(path):
            return False

        def func(server, base_url):
            with HTTPSession() as session:
                result = session.download_file(
                    base_url + "dummy", dest=".", validate=validate
                )
                assert result is None

        run_server(ContentDispoHandler, func)

    def test_error(self, socket_enabled):
        def func(server, base_url):
            with HTTPSession() as session:
                result = session.download_file(base_url + "dummy", dest=".")
                assert result is None

        run_server(ServerErrorHandler, func)

    def test_fallback(self, socket_enabled):
        def func(server, base_url):
            def inner_func(server2, base_url2):
                logging.info(f"servers: {base_url}, {base_url2}")
                with HTTPSession(base_urls=[base_url, base_url2]) as session:
                    session.set_max_retries(connect=4)
                    result = session.download_file(base_url + "dummy", dest=".")
                    assert result is not None
                    assert server.calls == 1
                    assert server2.tries == 2

            run_server(RetryHandler, inner_func)

        run_server(ServerErrorHandler, func)

    def test_content_abort(self, socket_enabled):
        def func(server, base_url):
            def inner_func(server2, base_url2):
                logging.info(f"servers: {base_url}, {base_url2}")
                with HTTPSession(base_urls=[base_url, base_url2]) as session:
                    session.DEFAULT_TIMEOUT = (10.0, 0.2)
                    session.set_max_retries(connect=4)
                    result = session.download_file("dummy", dest=".")
                    assert result is None
                    assert server.calls == 1
                    assert server2.tries == 1

            run_server(RetryAbortHandler, inner_func)

        run_server(ServerErrorHandler, func)

    def test_post_stream_data(self, socket_enabled):
        def outter_func(nok_server, nok_url):
            def func(server, url):
                with HTTPSession(base_urls=[nok_url, url]) as session:
                    session.DEFAULT_TIMEOUT = (3.0, 3.0)
                    with open("./data.txt", "wb") as fd:
                        fd.write(b"Hello!")
                    with open("./data.txt", "rb") as fd:
                        session.request(
                            "POST",
                            "dummy",
                            data_streams={
                                "data.txt": fd,
                                "str_metadata": "string",
                                "metadata": {"key1": "val1"},
                            },
                        )
                assert server.test_payloads["metadata"] == '{"key1": "val1"}'
                assert server.test_payloads["data.txt"] == "Hello!"
                assert server.test_payloads["str_metadata"] == "string"

            run_server(MultiPartPostHandler, func)

        run_server(ServerErrorHandler, outter_func)
