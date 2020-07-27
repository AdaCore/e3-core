from __future__ import annotations

import base64
import json
from e3.date import utc_timestamp


def get_payload(token: str) -> dict:
    """Get payload from a JSON Web Token.

    :param token: token
    :return: decoded payload
    """
    data = {}
    if token.count(".") == 2:
        # Extract the payload
        signing_part, _ = token.rsplit(".", 1)
        _, payload = signing_part.split(".", 1)
        # Add required padding
        rem = len(payload) % 4
        if rem > 0:
            payload += "=" * (4 - rem)
        try:
            data = json.loads(base64.urlsafe_b64decode(payload).decode("utf-8"))
        except (ValueError, TypeError):
            pass
    return data


def is_valid(token: str) -> bool:
    """Return true if the token is still valid, false otherwise.

    :param token: full token
    :return: return true if the token is still valid, false otherwise
    """
    payload = get_payload(token)

    # Given that we will use the token if valid, keep some margin and
    # do not consider a token valid if it will be valid less than 5 min
    deadline = utc_timestamp() + 5 * 60

    return payload.get("exp", 0) > deadline
