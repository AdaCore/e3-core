# prolog file loaded before all specs


def main():
    import yaml
    import os

    with open(os.path.join(
            __spec_repository.spec_dir, 'conf.yaml')) as f:
        conf = yaml.load(f)
        __spec_repository.api_version = conf['api_version']


main()
del main
