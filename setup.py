from setuptools import setup, find_packages

import os

install_requires = [
    "colorama",
    "pyyaml",
    "python-dateutil",
    "requests",
    "requests_toolbelt",
    "tqdm",
    "stevedore>1.20.0",
]

extras_require = {"config": ["tomlkit", "typeguard"]}

for p in ("darwin", "linux", "linux2", "win32"):
    platform_string = ":sys_platform=='%s'" % p
    extras_require[platform_string] = ["psutil"]
    if p in ("linux", "linux2"):
        extras_require[platform_string].append("ld")

# Get e3 version from the VERSION file.
version_file = os.path.join(os.path.dirname(__file__), "VERSION")
with open(version_file) as f:
    e3_version = f.read().strip()

with open(os.path.join(os.path.dirname(__file__), "README.md")) as f:
    long_description = f.read()

setup(
    name="e3-core",
    version=e3_version,
    url="https://github.com/AdaCore/e3-core",
    license="GPLv3",
    author="AdaCore",
    author_email="info@adacore.com",
    description="E3 core. Tools and library for building and testing software",
    long_description=long_description,
    long_description_content_type="text/markdown",
    namespace_packages=["e3"],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Topic :: Software Development :: Build Tools",
    ],
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    package_data={"e3": ["py.typed", "os/data/rlimit-*"]},
    install_requires=install_requires,
    extras_require=extras_require,
    entry_points={
        "e3.anod.sandbox.sandbox_action": [
            "exec = e3.anod.sandbox.action:SandBoxExec",
            "create = e3.anod.sandbox.action:SandBoxCreate",
            "show-config = e3.anod.sandbox.action:SandBoxShowConfiguration",
            "migrate = e3.anod.sandbox.migrate:SandBoxMigrate",
        ],
        "e3.event.handler": [
            "smtp = e3.event.handler.smtp:SMTPHandler",
            "logging = e3.event.handler.logging:LoggingHandler",
            "file = e3.event.handler.file:FileHandler",
            "s3 = e3.event.handler.s3:S3Handler",
        ],
        "e3.store": [
            "http-simple-store = e3.store.backends." "http_simple_store:HTTPSimpleStore"
        ],
        "e3.store.cache.backend": [
            "file-cache = e3.store.cache.backends.filecache:FileCache"
        ],
        "sandbox_scripts": ["anod = e3.anod.sandbox.scripts:anod"],
        "console_scripts": [
            "e3 = e3.sys:main",
            "e3-sandbox = e3.anod.sandbox.main:main",
        ],
    },
)
