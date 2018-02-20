from __future__ import absolute_import, division, print_function

import os.path

from e3.net.token import is_valid, read_jwt

TESTS_E3_DIR = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
TOKEN_PATH = os.path.join(TESTS_E3_DIR, 'data', 'token_file')
FUTURE_TIMESTAMP = 9999999999999


def test_valid_token():
    payload = {u'typ': u'Bearer', u'exp': FUTURE_TIMESTAMP}
    if is_valid(payload):
        assert True
    else:
        assert False


def test_wrong_token_type():
    payload = {u'typ': u'badtype', u'exp': FUTURE_TIMESTAMP}
    if is_valid(payload):
        assert False
    else:
        assert True


def test_old_token():
    payload = {u'typ': u'Bearer', u'exp': 1419064452}
    if is_valid(payload):
        assert False
    else:
        assert True


def test_read_token():
    _, payload = read_jwt(TOKEN_PATH)
    expected = {u'GivenName': u'Toto',
                u'Email': u'toto@example.com',
                u'Role': u'tester',
                u'iss': u'adacore.com',
                u'sub': u'test',
                u'exp': 1550655711,
                u'iat': 1519119711,
                u'Surname': u'123',
                u'aud': u'www.adacore.com'}
    assert payload == expected
