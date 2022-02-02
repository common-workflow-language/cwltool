FROM python:3.10-alpine as builder

RUN apk add --no-cache git gcc python3-dev libxml2-dev libxslt-dev libc-dev linux-headers

WORKDIR /cwltool
COPY . .

RUN pip install toml -rmypy-requirements.txt "$(grep ruamel requirements.txt)" \
	"$(grep schema.salad requirements.txt)"
# schema-salad is needed to be installed (this time as pure Python) for
# cwltool + mypyc
RUN CWLTOOL_USE_MYPYC=1 MYPYPATH=typeshed pip wheel --no-binary schema-salad --wheel-dir=/wheels .[deps]
RUN rm /wheels/schema_salad*
RUN pip install black
RUN SCHEMA_SALAD_USE_MYPYC=1 MYPYPATH=typeshed pip wheel --no-binary schema-salad \
	$(grep schema.salad requirements.txt) black --wheel-dir=/wheels
RUN pip install --force-reinstall --no-index --no-warn-script-location --root=/pythonroot/ /wheels/*.whl
# --force-reinstall to install our new mypyc compiled schema-salad package

FROM python:3.10-alpine as module
LABEL maintainer peter.amstutz@curri.com

RUN apk add --no-cache docker nodejs graphviz libxml2 libxslt
COPY --from=builder /pythonroot/ /

FROM python:3.10-alpine
LABEL maintainer peter.amstutz@curri.com

RUN apk add --no-cache docker nodejs graphviz libxml2 libxslt
COPY --from=builder /pythonroot/ /
COPY cwltool-in-docker.sh /cwltool-in-docker.sh

WORKDIR /error

ENTRYPOINT ["/cwltool-in-docker.sh"]
