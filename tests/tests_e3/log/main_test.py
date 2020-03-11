import datetime
import sys

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
