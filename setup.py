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
      url="https://github.com/common-workflow-language/cwltool",
      download_url="https://github.com/common-workflow-language/cwltool",
      license='Apache 2.0',
      packages=["cwltool"],
      package_data={'cwltool': ['schemas/draft-2/*.yml',
                                'schemas/draft-3/*.yml',
                                'schemas/draft-3/*.md',
                                'schemas/draft-3/salad/schema_salad/metaschema/*.yml',
                                'schemas/draft-3/salad/schema_salad/metaschema/*.md',
                                'schemas/v1.0/*.yml',
                                'schemas/v1.0/*.md',
                                'schemas/v1.0/salad/schema_salad/metaschema/*.yml',
                                'schemas/v1.0/salad/schema_salad/metaschema/*.md',
                                'schemas/v1.1.0-dev1/*.yml',
                                'schemas/v1.1.0-dev1/*.md',
                                'schemas/v1.1.0-dev1/salad/schema_salad/metaschema/*.yml',
                                'schemas/v1.1.0-dev1/salad/schema_salad/metaschema/*.md',
                                'cwlNodeEngine.js']},
      install_requires=[
          'requests',
          'ruamel.yaml == 0.12.4',
          'rdflib >= 4.1.0',
          'rdflib-jsonld >= 0.3.0',
          'shellescape',
          'schema-salad >= 1.18.20161005190847',
          'typing >= 3.5.2',
          'cwltest >= 1.0.20160907111242'],
      test_suite='tests',
      tests_require=[],
      entry_points={
          'console_scripts': [ "cwltool=cwltool.main:main" ]
      },
      zip_safe=True,
      cmdclass={'egg_info': tagger},
)
