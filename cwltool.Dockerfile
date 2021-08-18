FROM python:3.9-slim as builder

RUN apt-get update && apt-get install -y \
	gcc \
	git \
	libc-dev \
	libxml2-dev \
	libxslt1-dev \
	python3-dev \
  && rm -rf /var/lib/apt/lists/*
#	linux-headers \

WORKDIR /cwltool
COPY . .

RUN python setup.py bdist_wheel --dist-dir=/wheels
RUN pip wheel -r requirements.txt --wheel-dir=/wheels
RUN pip install --no-index --no-warn-script-location --root=/pythonroot/ /wheels/*.whl

FROM python:3.9-slim as module
LABEL maintainer peter.amstutz@curii.com

RUN apt-get update && apt-get install -y \
	docker.io \
	graphviz \
	libxml2 \
	libxslt1.1 \
	nodejs \
  && rm -rf /var/lib/apt/lists/*
COPY --from=builder /pythonroot/ /

FROM python:3.9-slim
LABEL maintainer peter.amstutz@curii.com

RUN apt-get update && apt-get install -y \
	docker.io \
	graphviz \
	libxml2 \
	libxslt1.1 \
	nodejs \
  && rm -rf /var/lib/apt/lists/*
COPY --from=builder /pythonroot/ /
COPY cwltool-in-docker.sh /cwltool-in-docker.sh

WORKDIR /error

ENTRYPOINT ["/cwltool-in-docker.sh"]
