from __future__ import annotations

# The following two functions are used during transition of qualifiers
# from str representation to dict by default


def qualifier_dict_to_str(qual: dict) -> str:
    """Serialize a dict qualifier into a str.

    :param qual: dict qualifier
    :return: a deterministic str that represent the dict qualifier
    """
    tmp = []
    for k, v in qual.items():
        if isinstance(v, str):
            if v:
                tmp.append(f"{k}={v}")
            else:
                # Empty string is used also for tag value. Should be removed
                # once switch to dict is complete
                tmp.append(k)
        elif isinstance(v, bool):
            if v:
                tmp.append(k)
        elif v:
            tmp.append(f"{k}=" + ";".join(sorted(v)))

    return ",".join(sorted(tmp))


def qualifier_str_to_dict(qual: str | None) -> dict:
    """Parse a str qualifier into a dict.

    :param qual: a string representing a qualifier
    :return: a dict qualifier
    """
    if not qual:
        return {}

    result: dict[str, str | bool] = {}

    for key, sep, value in (item.partition("=") for item in qual.split(",")):
        if sep == "=":
            if value:
                result[key] = value
            else:
                result[key] = ""
        else:
            # Replace by bool once switch to dict is complete
            result[key] = ""
    return result
