FROM python:3-alpine
LABEL maintainer="Daniel Perna <danielperna84@gmail.com>"

RUN apk update && \
    apk upgrade && \
    apk add --no-cache bash git openssh && \
    pip install --no-cache-dir gitpython pyotp

WORKDIR /app
COPY configurator.py /app/

EXPOSE 3218
VOLUME /config

ENV HC_GIT true
ENV HC_BASEPATH /config

ENTRYPOINT ["python", "/app/configurator.py"]