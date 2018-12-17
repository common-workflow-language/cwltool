#!/bin/bash

if [[ $TRAVIS_OS_NAME == 'linux' ]]; then
    wget -O- http://neuro.debian.net/lists/trusty.us-nh.full | sudo tee /etc/apt/sources.list.d/neurodebian.sources.list;
    sudo apt-key add .travis.singularity_key.txt;
    sudo apt-get update;
    sudo apt-get install -y singularity-container;
elif [[ $TRAVIS_OS_NAME == 'osx' ]]; then
    if [[ $TRAVIS_PYTHON_VERSION == '2.7' ]]; then
        PKG_URL='https://www.python.org/ftp/python/2.7.15/python-2.7.15-macosx10.9.pkg'
    elif [[ $TRAVIS_PYTHON_VERSION == '3.4' ]]; then
        PKG_URL='https://www.python.org/ftp/python/3.4.4/python-3.4.4-macosx10.6.pkg'
    fi
    wget $PKG_URL -O install_python.pkg;
    sudo installer -pkg install_python.pkg -target /
    which python;
    python --version;
fi