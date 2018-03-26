from __future__ import absolute_import, division, print_function

import base64
import calendar
import json
from datetime import datetime


def get_payload(token):
    """Get payload from a JSON Web Token.

    :param token: token
    :type token: str
    :return: decoded payload
    :rtype: dict
    """
    data = {}
    if token.count('.') == 2:
        # Extract the payload
        signing_part, _ = token.rsplit('.', 1)
        _, payload = signing_part.split('.', 1)
        # Add required padding
        rem = len(payload) % 4
        if rem > 0:
            payload += '=' * (4 - rem)
        try:
            data = json.loads(base64.b64decode(payload).decode('utf-8'))
        except (UnicodeDecodeError, ValueError, TypeError):
            pass
    return data


def utc_timestamp():
    """Return the number of seconds since epoch UTC.

    :return: the number of seconds since epoch UTC
    :rtype: int
    """
    d = datetime.utcnow()
    return calendar.timegm(d.utctimetuple())


def is_valid(token):
    """Return true if the token is still valid, false otherwise.

    :param token: full token
    :type token: str
    :return: return true if the token is still valid, false otherwise
    :rtype: bool
    """
    payload = get_payload(token)
    return payload.get('typ') == 'Bearer' and \
        payload.get('exp', 0) > utc_timestamp()
