import datetime
import sys
import json
import dateutil.parser
import e3.log
import e3.os.process


def test_log():
    p = e3.os.process.Run(
        [
            sys.executable,
            "-c",
            "\n".join(
                (
                    "import e3.log",
                    'e3.log.activate(filename="log.txt")',
                    'l = e3.log.getLogger("test_log")',
                    'l.debug("this is a log record")',
                )
            ),
        ]
    )
    assert p.status == 0

    with open("log.txt") as f:
        line = f.readline()
        # Get datetime in the log
        log_datetime, _, _ = line.partition(": ")

        # Parse it and verify that it is it in GMT
        assert (
            datetime.datetime.utcnow() - dateutil.parser.parse(log_datetime)
        ).seconds < 10


def test_json_log():
    p = e3.os.process.Run(
        [
            sys.executable,
            "-c",
            "\n".join(
                (
                    "import e3.log",
                    'e3.log.activate(filename="log.json",json_format=True)',
                    "e3.log.add_formatter_attr(['size'])",
                    'l = e3.log.getLogger("test_log")',
                    'l.debug("this is a log record")',
                    "l.debug(\"extra key\",extra={'size':'100'})",
                )
            ),
        ]
    )

    assert p.status == 0

    with open("log.json") as f:
        lines = f.readlines()

    record = json.loads(lines[0])
    # verify if we get default json fields
    assert len(record.keys()) == 5

    # verify presence of custom size field
    record = json.loads(lines[1])
    assert "size" in record


def test_json_log_compat():
    """we make sure that code do not crash if json is not activated."""
    p = e3.os.process.Run(
        [
            sys.executable,
            "-c",
            "\n".join(
                (
                    "import e3.log",
                    'e3.log.activate(filename="log.json")',
                    "e3.log.add_formatter_attr(['size'])",
                    'l = e3.log.getLogger("test_log")',
                    'l.debug("this is a log record")',
                    "l.debug(\"extra key\",extra={'size':'100'})",
                )
            ),
        ]
    )

    assert p.status == 0
