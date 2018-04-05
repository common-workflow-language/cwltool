FROM python:3.6-alpine as builder

RUN apk add --no-cache git

WORKDIR /cwltool
COPY . .

RUN python setup.py bdist_wheel --dist-dir=/wheels
RUN pip wheel -r requirements.txt --wheel-dir=/wheels
RUN pip install --use-wheel --no-index --root=/pythonroot/ /wheels/*.whl

FROM python:3.6-alpine
LABEL maintainer peter.amstutz@curoverse.com

RUN apk add --no-cache docker nodejs
COPY --from=builder /pythonroot/ /
COPY cwltool-in-docker.sh /cwltool-in-docker.sh

WORKDIR /error

ENTRYPOINT ["/cwltool-in-docker.sh"]
