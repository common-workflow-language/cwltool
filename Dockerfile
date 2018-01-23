FROM docker:18.01.0-ce
LABEL maintainer peter.amstutz@curoverse.com

ADD setup.py README.rst cwltool/ /root/cwltool/
ADD cwltool/ /root/cwltool/cwltool
ADD cwltool/schemas/ /root/cwltool/cwltool/schemas
ADD tests/ /root/cwltool/tests
RUN apk add --no-cache python py-pip && \
    apk add --no-cache --virtual devtools gcc libc-dev python-dev && \
    pip install -U pip setuptools wheel && \
    pip install /root/cwltool && \
    apk del devtools

ENTRYPOINT ["cwltool"]
