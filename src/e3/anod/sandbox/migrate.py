"""Convert to Anod newer API."""


from __future__ import annotations

from e3.anod.error import SandBoxError
from e3.anod.sandbox.action import SandBoxAction
from e3.os.fs import cd


class SandBoxMigrate(SandBoxAction):

    name = "migrate"
    help = "Migrate to a newer anod API version"
    require_sandbox = False

    def add_parsers(self) -> None:
        self.parser.add_argument("api_version", help="API version")
        self.parser.add_argument("spec_dir", help="Path to spec directory")

    def run(self, args):
        if args.api_version != "1.5":
            raise SandBoxError("Only 1.5 is supported for now")
        cd(args.spec_dir)
        migrate_v1_5()


def migrate_v1_5() -> None:
    """Migrate to API 1.5.

    Move all .yaml files in subdirs, when the name of a yaml
    file matches a spec name move the yaml file in
    <spec name>/config.yaml

    When there is an additional suffix, move it to

    <spec name>/<suffix>.yaml

    Make sure to run e3-plan-checker after running this script.
    """
    from glob import glob
    import os
    from e3.fs import mv

    for f in glob("*.yaml"):
        print(f"looking at {f}")
        name, _ = os.path.splitext(os.path.basename(f))
        if os.path.exists(name + ".anod"):
            try:
                os.mkdir(name)
            except OSError:
                pass
            try:
                mv(name + ".yaml", os.path.join(name, "config.yaml"))
            except OSError:  # defensive code
                print(f"error for {name}")
        elif "-" in name:
            print(f"suffix detected in {f}")
            prefix, suffix = name.rsplit("-", 1)
            if not os.path.exists(prefix + ".anod"):
                prefix, suffix2 = prefix.rsplit("-", 1)
                suffix = suffix2 + "-" + suffix
            try:
                try:
                    os.mkdir(prefix)
                except OSError:  # defensive code
                    pass
                mv(name + ".yaml", os.path.join(prefix, f"{suffix}.yaml"))
            except Exception as er:  # defensive code
                print(f"error for {name}.yaml {prefix} {suffix}")
                print(er)
        else:
            print(f"unknown yaml file {name}.yaml")
