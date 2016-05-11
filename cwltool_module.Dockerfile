FROM ubuntu:14.04
MAINTAINER peter.amstutz@curoverse.com

# Based on https://github.com/jpetazzo/dind

# Let's start with some basic stuff.
RUN apt-get update -qq && apt-get install -qqy \
    python-setuptools gcc python-dev

# Install cwltool
ADD setup.py README.rst cwltool/ /root/cwltool/
ADD cwltool/ /root/cwltool/cwltool
ADD cwltool/schemas/ /root/cwltool/cwltool/schemas
RUN cd /root/cwltool && easy_install .
