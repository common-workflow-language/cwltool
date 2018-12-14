#!/bin/bash

if [[ $TRAVIS_OS_NAME == 'linux' ]]; then
    wget -O- http://neuro.debian.net/lists/trusty.us-nh.full | sudo tee /etc/apt/sources.list.d/neurodebian.sources.list;
    sudo apt-key add .travis.singularity_key.txt;
    sudo apt-get update;
    sudo apt-get install -y singularity-container;
elif [[ $TRAVIS_OS_NAME == "osx" ]]; then
    brew install pyenv-virtualenv
    pyenv install $PYENV_VERSION
    pyenv virtualenv $PYENV_VERSION venv
    source $(pyenv root)/versions/venv/bin/activate
fi