#!/usr/bin/env python

import os
import sys
import shutil

import setuptools.command.egg_info as egg_info_cmd
from setuptools import setup, find_packages

SETUP_DIR = os.path.dirname(__file__)
README = os.path.join(SETUP_DIR, 'README.rst')

try:
    import gittaggers
    tagger = gittaggers.EggInfoFromGit
except ImportError:
    tagger = egg_info_cmd.egg_info

setup(name='cwltool',
      version='1.0',
      description='Common workflow language reference implementation',
      long_description=open(README).read(),
      author='Common workflow language working group',
      author_email='common-workflow-language@googlegroups.com',
      url="https://github.com/common-workflow-language/common-workflow-language",
      download_url="https://github.com/common-workflow-language/common-workflow-language",
      license='Apache 2.0',
      packages=["cwltool"],
      package_data={'cwltool': ['schemas/draft-2/*.yml',
                                'schemas/draft-3/*.yml',
                                'schemas/draft-3/*.md',
                                'schemas/draft-3/salad/schema_salad/metaschema/*.yml',
                                'schemas/draft-3/salad/schema_salad/metaschema/*.md',
                                'schemas/draft-4/*.yml',
                                'schemas/draft-4/*.md',
                                'schemas/draft-4/salad/schema_salad/metaschema/*.yml',
                                'schemas/draft-4/salad/schema_salad/metaschema/*.md']},
      install_requires=[
          'requests',
          'PyYAML',
          'rdflib >= 4.1.0',
          'rdflib-jsonld >= 0.3.0',
          'shellescape',
          'schema-salad==1.11.20160506154702',
          'typing'
        ],
      test_suite='tests',
      tests_require=[],
      entry_points={
          'console_scripts': [ "cwltool=cwltool.main:main", "cwltest=cwltool.cwltest:main" ]
      },
      zip_safe=True,
      cmdclass={'egg_info': tagger},
)
