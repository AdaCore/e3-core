from setuptools import setup, find_packages

import os
import re
import subprocess
import sys

install_requires = [
    'clint',
    'netifaces',
    'pyyaml',
    'python-dateutil',
    'requests',
    'stevedore']

if sys.platform in ('linux2', 'linux', 'win32', 'darwin'):
    install_requires.append('psutil')

# Get E3 version using git describe and store it in a VERSION file.
# When building from a source package, reads the version from the VERSION file.
version_file = os.path.join(os.path.dirname(__file__), 'VERSION')

GIT_DESC_RE = r'^v(?P<ver>.*?)-(?P<commits>\d+)-g(?P<full>[\da-f]+)$'

try:
    git_version = subprocess.check_output([
        'git', 'describe', '--long',
        '--match', 'v[0-9]*.[0-9]*.[0-9]*']).strip()

except Exception:
    with open(version_file) as f:
        e3_version = f.read().strip()

else:

    # Generate a version number that conforms to the versioning scheme defined
    # in PEP 286 ('N.N[.N]+[{a|b|c|rc}N[.N]+][.postN][.devN]')

    version_m = re.search(GIT_DESC_RE, git_version)
    if version_m is None:
        raise ValueError('git describe does not returns a valid version')

    # Get number of additional commit since last tag
    nb_commits = int(version_m.group('commits'))
    e3_version = version_m.group('ver')
    with open(version_file, 'w') as f:
        f.write(e3_version + '\n')

setup(
    name='e3-core',
    version=e3_version,
    url='https://github.com/AdaCore/e3-core',
    license='GPLv3',
    author='AdaCore',
    author_email='info@adacore.com',
    description='E3 core. Tools and library for building and testing software',
    namespace_packages=['e3'],
    use_2to3=True,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience:: Developers',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.4',
        'Topic :: Software Development :: Build Tools'],
    packages=find_packages(),
    package_data={
        'e3': ['os/data/rlimit-*']},
    install_requires=install_requires,
    entry_points={
        'e3.anod.sandbox.sandbox_action': [
            'create = e3.anod.sandbox:SandBoxCreate',
            'show-config = e3.anod.sandbox:SandBoxShowConfiguration',
        ],
        'e3.store': [
            'http-simple-store = e3.store.backends.'
            'http_simple_store:HTTPSimpleStore',
        ],
        'e3.store.cache.backend': [
            'file-cache = e3.store.cache.backends.filecache:FileCache',
        ],
        'sandbox_scripts': [
            'anod = e3.anod.sandbox.scripts:anod',
        ],
        'console_scripts': [
            'e3 = e3.sys:main',
            'e3-sandbox = e3.anod.sandbox:main',
        ]})
