#!/bin/bash

if [[ $TRAVIS_OS_NAME == 'linux' ]]; then
    wget -O- http://neuro.debian.net/lists/trusty.us-nh.full | sudo tee /etc/apt/sources.list.d/neurodebian.sources.list;
    sudo apt-key add .travis.singularity_key.txt;
    sudo apt-get update;
    sudo apt-get install -y singularity-container;
elif [[ $TRAVIS_OS_NAME == "osx" ]]; then
    wget https://www.python.org/ftp/python/$TRAVIS_PYTHON_VERSION/python-$TRAVIS_PYTHON_VERSION-macosx10.9.pkg -O install_python.pkg;
    sudo installer -pkg install_python.pkg -target /
    which python;
    python --version;
fi