from __future__ import absolute_import, division, print_function

import calendar
import json
from datetime import datetime


def read_jwt(filename):
    """Read a jwt token.

    :param filename: jwt token path
    :type filename: str

    :return: a tuple containing the jwt raw content and the decoded payload
    :rtype: (str, dict)
    """
    with open(filename, 'rb') as f:
        jwt = f.read()

    # Extract the payload
    signing_part, _ = jwt.rsplit(b'.', 1)
    _, payload = signing_part.split(b'.', 1)

    # Add required padding
    rem = len(payload) % 4
    if rem > 0:
        payload += b'=' * (4 - rem)
    return jwt, json.loads(payload.decode('base64'))


def utc_timestamp():
    """Return the number of seconds since epoch UTC."""
    d = datetime.utcnow()
    return calendar.timegm(d.utctimetuple())


def is_valid(token):
    """Return true if the token is still valid, false otherwise."""
    return token.get('typ') == 'Bearer' and \
        token.get('exp', 0) > utc_timestamp()
