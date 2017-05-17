#!/usr/bin/env python

import os

from setuptools import setup, find_packages

SETUP_DIR = os.path.dirname(__file__)
README = os.path.join(SETUP_DIR, 'README.md')

setup(
    name='cwltool-tes',
    version='0.1',
    description='Common workflow language reference implementation backended \
    by a GA4GH Task Execution Service',
    long_description=open(README).read(),
    author='Common workflow language working group',
    author_email='common-workflow-language@googlegroups.com',
    url="https://github.com/common-workflow-language/cwltool-tes",
    download_url="https://github.com/common-workflow-language/cwltool-tes",
    license='Apache 2.0',
    install_requires=[
        'cwltool==1.0.20170510165748'
    ],
    entry_points={
        'console_scripts': ["cwltool-tes=cwltool_tes.main:main"]},
    zip_safe=True
)
