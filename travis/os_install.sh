#!/bin/bash

if [[ $TRAVIS_OS_NAME == 'linux' ]]; then
    wget -O- http://neuro.debian.net/lists/trusty.us-nh.full | sudo tee /etc/apt/sources.list.d/neurodebian.sources.list;
    sudo apt-key add .travis.singularity_key.txt;
    sudo apt-get update;
    sudo apt-get install -y singularity-container;
elif [[ $TRAVIS_OS_NAME == "osx" ]]; then
    export TOXENV=$TRAVIS_PYTHON_VERSION
    brew update
    brew install openssl readline
    # See https://docs.travis-ci.com/user/osx-ci-environment/#A-note-on-upgrading-packages.
    # I didn't do this above because it works and I'm lazy.
    brew outdated pyenv || brew upgrade pyenv
    # virtualenv doesn't work without pyenv knowledge. venv in Python 3.3
    # doesn't provide Pip by default. So, use `pyenv-virtualenv <https://github.com/yyuu/pyenv-virtualenv/blob/master/README.md>`_.
    brew install pyenv-virtualenv
    pyenv install $PYENV_VERSION
    # I would expect something like ``pyenv init; pyenv local $PYTHON`` or
    # ``pyenv shell $PYTHON`` would work, but ``pyenv init`` doesn't seem to
    # modify the Bash environment. ??? So, I hand-set the variables instead.
    export PATH="/Users/travis/.pyenv/shims:${PATH}"
    pyenv-virtualenv venv
    source venv/bin/activate
    # A manual check that the correct version of Python is running.
    python --version
fi