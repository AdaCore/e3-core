from __future__ import absolute_import
from setuptools import setup, find_packages
from datetime import datetime

import os
import sys

install_requires = [
    'clint',
    'enum34',
    'netifaces',
    'pyyaml',
    'python-dateutil',
    'requests',
    'stevedore']

if sys.platform in ('linux2', 'linux', 'win32', 'darwin'):
    install_requires.append('psutil')

if sys.platform in ('linux', 'linux2'):
    install_requires.append('ld')

# Get e3 version from the VERSION file.
version_file = os.path.join(os.path.dirname(__file__), 'VERSION')
with open(version_file) as f:
    e3_version = f.read().strip()

# If the version contains only the two first digits, add the date in
# YYYYMMDD format to create a version following PEP 286:
# 'N.N[.N]+[{a|b|c|rc}N[.N]+][.postN][.devN]'
if e3_version.count('.') == 1:
    e3_version = e3_version + '.' + datetime.utcnow().strftime('%Y%m%d')

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
            'create = e3.anod.sandbox.action:SandBoxCreate',
            'show-config = e3.anod.sandbox.action:SandBoxShowConfiguration',
        ],
        'e3.event.manager': [
            'smtp = e3.event.backends.smtp:SMTPEventManager'
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
            'e3-sandbox = e3.anod.sandbox.main:main',
        ]})
