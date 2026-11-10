FROM python:3.15-alpine3.24 as builder

ARG VERSION=0.0.0

RUN apk add --no-cache git gcc python3-dev libxml2-dev libxslt-dev libc-dev linux-headers

WORKDIR /cwltool
COPY . .
RUN export SETUPTOOLS_SCM_PRETEND_VERSION_FOR_CWLTOOL=${VERSION} ; \
  CWLTOOL_USE_MYPYC=1 MYPYPATH=mypy-stubs pip wheel --no-binary schema-salad \
  --wheel-dir=/wheels .[deps]  --verbose
RUN rm /wheels/schema_salad*
RUN SCHEMA_SALAD_USE_MYPYC=1 MYPYPATH=mypy-stubs pip wheel \
  --no-binary schema-salad $(grep schema.salad requirements.txt) \
  --wheel-dir=/wheels  --verbose
RUN pip install --root-user-action ignore --force-reinstall --no-index --no-warn-script-location \
	--root=/pythonroot/ /wheels/*.whl
# --force-reinstall to install our new mypyc compiled schema-salad package

FROM python:3.15-alpine3.24 as module

RUN apk add --no-cache docker nodejs graphviz libxml2 libxslt
COPY --from=builder /pythonroot/ /

FROM python:3.15-alpine3.24

RUN apk add --no-cache docker nodejs graphviz libxml2 libxslt
COPY --from=builder /pythonroot/ /
COPY cwltool-in-docker.sh /cwltool-in-docker.sh

WORKDIR /error

ENTRYPOINT ["/cwltool-in-docker.sh"]
