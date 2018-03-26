from __future__ import absolute_import, division, print_function

import base64
import hashlib
import json

from e3.net.token import get_payload, is_valid

FUTURE_TIMESTAMP = 9999999999999


def create_token(payload):
    """Return JSON Web Token.

    :param payload:
    :type payload: dict
    :return: token
    :rtype: str
    """
    payload_bytes = json.dumps(payload).encode('utf-8')
    data = b'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9' + b'.'\
           + base64.b64encode(payload_bytes)
    signature = hashlib.sha256(data).hexdigest().encode('utf-8')
    token = data + b'.' + signature
    return token.decode('utf-8')


def test_get_payload():
    expected = {u'GivenName': u'Toto',
                u'Email': u'toto@example.com',
                u'Role': u'tester',
                u'iss': u'adacore.com',
                u'sub': u'test',
                u'exp': 1550655711,
                u'iat': 1519119711,
                u'Surname': u'123',
                u'aud': u'www.adacore.com'}
    token = create_token(expected)
    payload = get_payload(token)
    assert payload == expected


def test_valid_token():
    valid_token = create_token(
        {u'typ': u'Bearer', u'exp': FUTURE_TIMESTAMP})
    assert is_valid(valid_token)


def test_wrong_token_type():
    badtype_token = create_token(
        {u'typ': u'badtype', u'exp': FUTURE_TIMESTAMP})
    assert not is_valid(badtype_token)


def test_old_token():
    old_token = create_token(
        {u'typ': u'Bearer', u'exp': 1419064452})
    assert not is_valid(old_token)


def test_exception_pass():
    assert not is_valid('..')


def test_token_str():
    token = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJhZGFjb3JlLmNvbSI'\
            'sImlhdCI6MTUxOTExOTcxMSwiZXhwIjoxNTUwNjU1NzExLCJhdWQiOiJ3d3cuYWR'\
            'hY29yZS5jb20iLCJzdWIiOiJ0ZXN0IiwiR2l2ZW5OYW1lIjoiVG90byIsIlN1cm5'\
            'hbWUiOiIxMjMiLCJFbWFpbCI6InRvdG9AZXhhbXBsZS5jb20iLCJSb2xlIjoidGV'\
            'zdGVyIn0.UERDJuUFh6A30TXIEKbNu6BbDOUCdsLGMKuQS8DfboA'
    payload = get_payload(token)
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
    assert not is_valid(token)
