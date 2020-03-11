import e3.os.process
import e3.sys


def test_main():
    assert e3.sys.version() in e3.os.process.Run(["e3", "--version"]).out
    assert "Everything OK!" in e3.os.process.Run(["e3", "--check"]).out
