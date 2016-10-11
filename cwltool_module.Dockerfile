FROM ubuntu:14.04
MAINTAINER peter.amstutz@curoverse.com

# Let's start with some basic stuff.
RUN apt-get update -qq && \
    DEBIAN_FRONTEND=noninteractive apt-get install -qy --no-install-recommends \
        python-setuptools build-essential python-dev python-pip

# Install cwltool
ADD setup.py README.rst cwltool/ /root/cwltool/
ADD cwltool/ /root/cwltool/cwltool
ADD cwltool/schemas/ /root/cwltool/cwltool/schemas
RUN cd /root/cwltool && pip install .
