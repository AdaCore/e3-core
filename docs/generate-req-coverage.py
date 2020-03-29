#!/usr/bin/env python
# type: ignore
"""Generate the requirement coverage for e3-core doc."""

import sys
import yaml


def lookup(item, d):
    """Lookup an item in a dictionary."""
    return {key for key, value in d.items() if value == item}


def merge_docs(requirement: str, coverage: str) -> dict:
    """Load requirement yaml and include the coverage info.

    :param requirement: yaml filename containing list of requirements
    :param coverage: yaml filename formatting as 'testname: requirement'
    """
    with open(requirement) as f:
        reqs = yaml.safe_load(f)

    with open(coverage) as f:
        reqs_cov = yaml.safe_load(f)

    for k in reqs:
        tests = lookup(k, reqs_cov)
        reqs[k]["tests"] = tests
    return reqs


def generate_rst(reqs_result: dict, dest: str):
    """Generate rst file from requirement coverage data.

    :param reqs_result: dictionary returned by merge_docs
    :param dest: rst file to create
    """
    with open(dest, "w") as f:
        for k in reqs_result:
            f.write("- %s\n" % k)
            f.write("  %s\n" % reqs_result[k]["desc"].encode("utf-8"))
            tests = reqs_result[k]["tests"]
            if tests:
                f.write("  **Covered by %s**\n" % ", ".join(reqs_result[k]["tests"]))
            else:
                f.write("  **Not yet covered**\n")


if __name__ == "__main__":
    generate_rst(merge_docs(sys.argv[1], sys.argv[2]), sys.argv[3])
