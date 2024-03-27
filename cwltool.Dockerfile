FROM python:3.12-alpine3.17 as builder

RUN apk add --no-cache git gcc python3-dev libxml2-dev libxslt-dev libc-dev linux-headers

WORKDIR /cwltool
COPY . .
RUN export SETUPTOOLS_SCM_PRETEND_VERSION_FOR_CWLTOOL=$(grep __version__ cwltool/_version.py  | awk -F\' '{ print $2 }' | tr -d '\\n') ; \
	CWLTOOL_USE_MYPYC=1 MYPYPATH=mypy-stubs pip wheel --no-binary schema-salad \
	--wheel-dir=/wheels .[deps]  # --verbose
RUN rm /wheels/schema_salad*
RUN pip install "black~=22.0"
# galaxy-util 22.1.x depends on packaging<22, but black 23.x needs packaging>22
RUN SCHEMA_SALAD_USE_MYPYC=1 MYPYPATH=mypy-stubs pip wheel --no-binary schema-salad \
	$(grep schema.salad requirements.txt) "black~=22.0" --wheel-dir=/wheels  # --verbose
RUN pip install --force-reinstall --no-index --no-warn-script-location \
	--root=/pythonroot/ /wheels/*.whl
# --force-reinstall to install our new mypyc compiled schema-salad package

FROM python:3.12-alpine3.17 as module
LABEL maintainer peter.amstutz@curii.com

RUN apk add --no-cache docker nodejs 'graphviz<8' libxml2 libxslt
COPY --from=builder /pythonroot/ /

FROM python:3.12-alpine3.17
LABEL maintainer peter.amstutz@curii.com

RUN apk add --no-cache docker nodejs 'graphviz<8' libxml2 libxslt
COPY --from=builder /pythonroot/ /
COPY cwltool-in-docker.sh /cwltool-in-docker.sh

WORKDIR /error

ENTRYPOINT ["/cwltool-in-docker.sh"]
