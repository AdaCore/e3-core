import base64
import hashlib
import json

from e3.net.token import get_payload, is_valid, utc_timestamp

FUTURE_TIMESTAMP = 9999999999999


def create_token(payload: dict) -> str:
    """Return JSON Web Token.

    :param payload:
    :return: token
    """
    payload_bytes = json.dumps(payload).encode("utf-8")
    data = b"eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9." + base64.b64encode(payload_bytes)
    signature = hashlib.sha256(data).hexdigest().encode("utf-8")
    token = data + b"." + signature
    return token.decode("utf-8")


def test_get_payload():
    expected = {
        "GivenName": "Toto",
        "Email": "toto@example.com",
        "Role": "tester",
        "iss": "adacore.com",
        "sub": "test",
        "exp": 1550655711,
        "iat": 1519119711,
        "Surname": "123",
        "aud": "www.adacore.com",
    }
    token = create_token(expected)
    payload = get_payload(token)
    assert payload == expected


def test_valid_token():
    valid_token = create_token({"exp": FUTURE_TIMESTAMP})
    assert is_valid(valid_token)

    near_future = utc_timestamp() + 7 * 60
    near_future_token = create_token({"exp": near_future})
    assert is_valid(near_future_token)


def test_old_token():
    old_token = create_token({"exp": 1419064452})
    assert not is_valid(old_token)

    # Verify that a token valid for less than 5 min will be considered invalid
    expire_soon_date = utc_timestamp() + 4 * 60
    expire_soon_token = create_token({"exp": expire_soon_date})
    assert not is_valid(expire_soon_token)


def test_exception_pass():
    assert not is_valid("..")


def test_token_str():
    token = (
        "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJhZGFjb3JlLmNvbSI"
        "sImlhdCI6MTUxOTExOTcxMSwiZXhwIjoxNTUwNjU1NzExLCJhdWQiOiJ3d3cuYWR"
        "hY29yZS5jb20iLCJzdWIiOiJ0ZXN0IiwiR2l2ZW5OYW1lIjoiVG90byIsIlN1cm5"
        "hbWUiOiIxMjMiLCJFbWFpbCI6InRvdG9AZXhhbXBsZS5jb20iLCJSb2xlIjoidGV"
        "zdGVyIn0.UERDJuUFh6A30TXIEKbNu6BbDOUCdsLGMKuQS8DfboA"
    )
    payload = get_payload(token)
    expected = {
        "GivenName": "Toto",
        "Email": "toto@example.com",
        "Role": "tester",
        "iss": "adacore.com",
        "sub": "test",
        "exp": 1550655711,
        "iat": 1519119711,
        "Surname": "123",
        "aud": "www.adacore.com",
    }
    assert payload == expected
    assert not is_valid(token)
