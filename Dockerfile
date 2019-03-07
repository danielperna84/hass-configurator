FROM python:3-alpine
LABEL maintainer="Daniel Perna <danielperna84@gmail.com>"

RUN apk update && \
    apk upgrade && \
    apk add --no-cache bash git openssh && \
    pip install --no-cache-dir hass-configurator

EXPOSE 3218
VOLUME /config

ENV HC_GIT true
ENV HC_BASEPATH /config

ENTRYPOINT ["hass-configurator"]