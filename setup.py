#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import re
import os.path as op


from codecs import open
from setuptools import setup, find_packages


def read(fname):
    ''' Return the file content. '''
    here = op.abspath(op.dirname(__file__))
    with open(op.join(here, fname), 'r', 'utf-8') as fd:
        return fd.read()

readme = read('README.rst')
changelog = read('CHANGES.rst').replace('.. :changelog:', '')

requirements = [
    #'tables',
    'pyzmq',
    'requests',
    'pyyaml'
]

version = ''
version = re.search(r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]',
                    read(op.join('colmet', '__init__.py')),
                    re.MULTILINE).group(1)

if not version:
    raise RuntimeError('Cannot find version information')


setup(
    name='colmet-collector',
    author="Olivier Richard",
    author_email='olivier.richard@imag.fr',
    version=version,
    url='https://github.com/oar-team/colmet-collector',
    # packages=find_packages(),
    packages=["colmet"],
    package_dir={'colmet': 'colmet'},
    package_data={'colmet': ['collector/metrics/*.yml']},
    install_requires=requirements,
    include_package_data=True,
    zip_safe=False,
    description="Metrics collector for Rust Colmet version",
    long_description=readme + '\n\n' + changelog,
    keywords='colmet-collector',
    license='GNU GPL',
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: BSD License',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: Implementation :: CPython',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: System :: Clustering',
    ],
    entry_points={
        'console_scripts': [
            'colmet-collector = colmet.collector.main:main',
            'colmet-node-config = colmet.node.configure:main',
        ],
    },
)
