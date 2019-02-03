#!/usr/bin/env python

from setuptools import setup

setup(
    name="boite",
    version="0.0.0",
    author='Ross Fenning',
    author_email='github@rossfenning.co.uk',
    packages=['boite'],
    description='Get things done with your mail box',
    install_requires=['clize', 'IMAPClient', 'progressbar33'],
    entry_points={
        'console_scripts': [
            'boite = boite.cli:main',
        ],
    },
)
