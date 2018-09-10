#!/usr/bin/env python
"""Setup for the reference implementation of the CWL standards."""
import os
import sys

import setuptools.command.egg_info as egg_info_cmd
from setuptools import setup

SETUP_DIR = os.path.dirname(__file__)
README = os.path.join(SETUP_DIR, 'README.rst')

try:
    import gittaggers

    Tagger = gittaggers.EggInfoFromGit
except ImportError:
    Tagger = egg_info_cmd.egg_info

needs_pytest = {'pytest', 'test', 'ptr'}.intersection(sys.argv)
pytest_runner = ['pytest-runner', 'pytest-cov'] if needs_pytest else []

setup(name='cwltool',
      version='1.0',
      description='Common workflow language reference implementation',
      long_description=open(README).read(),
      author='Common workflow language working group',
      author_email='common-workflow-language@googlegroups.com',
      url="https://github.com/common-workflow-language/cwltool",
      download_url="https://github.com/common-workflow-language/cwltool",
      # platforms='',  # empty as is conveyed by the classifier below
      # license='',  # empty as is conveyed by the classifier below
      packages=["cwltool", 'cwltool.tests'],
      package_dir={'cwltool.tests': 'tests'},
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
                                'cwlNodeEngine.js',
                                'cwlNodeEngineJSConsole.js',
                                'extensions.yml',
                                'hello.simg']},
      include_package_data=True,
      install_requires=[
          'setuptools',
          'requests >= 2.6.1',  # >= 2.6.1 to workaround
          # https://github.com/ionrock/cachecontrol/issues/137
          'ruamel.yaml >= 0.12.4, < 0.16',
          'rdflib >= 4.2.2, < 4.3.0',
          'shellescape >= 3.4.1, < 3.5',
          'schema-salad >= 2.7.20180905124720, < 3',
          'mypy-extensions',
          'six >= 1.9.0',  # >= 1.9.0 required by prov
          'psutil',
          'scandir',
          'prov == 1.5.1',
          'bagit >= 1.6.4',
          'typing-extensions',
      ],
      extras_require={
          ':os.name=="posix"': ['subprocess32 >= 3.5.0'],
          ':python_version<"3"': ['pathlib2 == 2.3.2'],
          ':python_version<"3.6"': ['typing >= 3.5.3'],
          'deps': ["galaxy-lib >= 17.09.3"]
      },
      python_requires='>=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*, <4',
      setup_requires=[] + pytest_runner,
      test_suite='tests',
      tests_require=['pytest', 'mock >= 2.0.0', 'pytest-mock >= 1.10.0', 'arcp >= 0.2.0', 'rdflib-jsonld >= 0.4.0'],
      entry_points={
          'console_scripts': ["cwltool=cwltool.main:run"]
      },
      zip_safe=True,
      cmdclass={'egg_info': Tagger},
      classifiers=[
          'Development Status :: 5 - Production/Stable',
          'Environment :: Console',
          'Intended Audience :: Developers',
          'Intended Audience :: Science/Research',
          'Intended Audience :: Healthcare Industry',
          'License :: OSI Approved :: Apache Software License',
          'Natural Language :: English',
          'Operating System :: MacOS :: MacOS X',
          'Operating System :: POSIX',
          'Operating System :: POSIX :: Linux',
          'Operating System :: OS Independent',
          'Operating System :: Microsoft :: Windows',
          'Operating System :: Microsoft :: Windows :: Windows 10',
          'Operating System :: Microsoft :: Windows :: Windows 8.1',
          # 'Operating System :: Microsoft :: Windows :: Windows 8',  # not tested
          # 'Operating System :: Microsoft :: Windows :: Windows 7',  # not tested
          'Programming Language :: Python :: 2',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.4',
          'Programming Language :: Python :: 3.5',
          'Programming Language :: Python :: 3.6',
          'Programming Language :: Python :: 3.7',
          'Topic :: Scientific/Engineering',
          'Topic :: Scientific/Engineering :: Bio-Informatics',
          'Topic :: Scientific/Engineering :: Astronomy',
          'Topic :: Scientific/Engineering :: Atmospheric Science',
          'Topic :: Scientific/Engineering :: Information Analysis',
          'Topic :: Scientific/Engineering :: Medical Science Apps.',
          'Topic :: System :: Distributed Computing',
          'Topic :: Utilities',
      ]
      )
