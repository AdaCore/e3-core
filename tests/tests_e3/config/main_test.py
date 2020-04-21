from dataclasses import dataclass
from e3.config import Config, ConfigSection


def test_config():
    with open("e3.toml", "w") as f:
        f.write(
            '[e3]\nfoo = 2\n  [e3.log]\n  pretty = false\n  stream_fmt = "%(message)s"'
        )

    Config.load_file("e3.toml")
    print(Config.data)

    @dataclass
    class MyConfig(ConfigSection):
        title = "e3.log"
        pretty: bool = True

    config = MyConfig.load()
    print(config)
    assert not config.pretty
