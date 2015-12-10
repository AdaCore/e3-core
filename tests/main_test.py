import e3.env
import e3.os.process


def test_main():
    assert e3.env.Env().build.platform in \
           e3.os.process.Run(['e3', '--platform-info=build']).out
