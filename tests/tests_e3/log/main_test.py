import datetime
import sys
import json
import dateutil.parser
import e3.log
import e3.os.process
from logging import LogRecord


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
    """test logger method wrappers and json logs."""
    p = e3.os.process.Run(
        [
            sys.executable,
            "-c",
            "\n".join(
                (
                    "import e3.log",
                    'e3.log.activate(filename="log.json",json_format=True)',
                    'l = e3.log.getLogger("test_log")',
                    'l.debug("this is a log record")',
                    'l.info("Log record with extra param", anod_uui=1212)',
                    'l.warning("Log record with extra param", anod_uui=1212)',
                    'l.debug("Log record with extra param", anod_uui=1212)',
                    'l.error("Log record with extra param", anod_uui=1212)',
                    'l.critical("Log record with extra param", anod_uui=1212)',
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
    for line in lines[1:]:
        record = json.loads(line)
        assert "anod_uui" in record
        assert len(record.keys()) == 6


def test_json_log_compat():
    """make sure that code do not crash if json is not activated."""
    p = e3.os.process.Run(
        [
            sys.executable,
            "-c",
            "\n".join(
                (
                    "import e3.log",
                    'e3.log.activate(filename="log.json")',
                    'l = e3.log.getLogger("test_log")',
                    'l.debug("this is a log record")',
                    'l.debug("extra key",anod_uui=121222)',
                )
            ),
        ]
    )

    assert p.status == 0


def test_json_log_exception():
    """test exception attribute support."""
    p = e3.os.process.Run(
        [
            sys.executable,
            "-c",
            "\n".join(
                (
                    "import e3.log",
                    'e3.log.activate(filename="log.json", json_format=True)',
                    'l = e3.log.getLogger("test_log")',
                    "try:",
                    "    1/0",
                    "except Exception as e:",
                    "    l.exception(e,exc_info=True)",
                )
            ),
        ]
    )

    assert p.status == 0

    with open("log.json") as f:
        lines = f.readlines()

    record = json.loads(lines[0])
    assert "exc_text" in record


def test_json_context():
    """test context attribute when console_logs is used."""
    p = e3.os.process.Run(
        [
            sys.executable,
            "-c",
            "\n".join(
                (
                    "import e3.log",
                    "e3.log.console_logs='test_json'",
                    'e3.log.activate(filename="log.json",json_format=True)',
                    'l = e3.log.getLogger("test_log")',
                    'l.debug("message")',
                )
            ),
        ]
    )

    assert p.status == 0

    with open("log.json") as f:
        lines = f.readlines()

    record = json.loads(lines[0])
    assert "context" in record
    assert record["context"] == "test_json"


def test_json_formatter():
    """test json formatter."""
    formatter = e3.log.JSONFormatter()
    record = LogRecord("_test_", 20, "module.py", 20, "Message", (), None)
    json_string = formatter.format(record)
    record_dict = json.loads(json_string)
    assert (len(record_dict.keys())) == 5
