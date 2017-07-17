#!/usr/bin/env python
from __future__ import absolute_import
import os

from setuptools import setup, find_packages

SETUP_DIR = os.path.dirname(__file__)
README = os.path.join(SETUP_DIR, 'README')

setup(name='cwlref-runner',
      version='1.0',
      description='Common workflow language reference implementation',
      long_description=open(README).read(),
      author='Common workflow language working group',
      author_email='common-workflow-language@googlegroups.com',
      url="http://www.commonwl.org",
      download_url="https://github.com/common-workflow-language/common-workflow-language",
      license='Apache 2.0',
      install_requires=[
          'cwltool'
        ],
      entry_points={
          'console_scripts': [ "cwl-runner=cwltool.main:main" ]
      },
      zip_safe=True
)
