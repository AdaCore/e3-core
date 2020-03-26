import e3.os.process
import e3.sys


def test_main():
    e3_tool = e3.sys.python_script("e3")
    assert e3.os.process.Run(e3_tool + ["--version"]).status == 0
    assert "Everything OK!" in e3.os.process.Run(e3_tool + ["--check"]).out
