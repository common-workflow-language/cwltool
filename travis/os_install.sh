#!/bin/bash

if [[ $TRAVIS_OS_NAME == 'linux' ]]; then
    wget -O- http://neuro.debian.net/lists/trusty.us-nh.full | sudo tee /etc/apt/sources.list.d/neurodebian.sources.list;
    sudo apt-key add .travis.singularity_key.txt;
    sudo apt-get update;
    sudo apt-get install -y singularity-container;
elif [[ $TRAVIS_OS_NAME == "osx" ]]; then
    pyenv install $PYENV_VERSION -s;
    eval "$(pyenv init -)";
    pyenv global $PYENV_VERSION;
    pip install -U virtualenv;
    VIRTUAL_ENV="$HOME/ve-pyenv-$PYENV_VERSION";
    virtualenv -p "$(which python)" ${VIRTUALENV_EXTRA_ARGS:-} "$VIRTUAL_ENV";
    source "$VIRTUAL_ENV/bin/activate";
fi