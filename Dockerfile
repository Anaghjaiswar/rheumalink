FROM python:3.13-alpine3.19
LABEL maintainer="londonappdeveloper.com"


ENV PYTHONUNBUFFERED=1
ENV PATH="/scripts:/py/bin:$PATH"

# creating venv early
RUN python -m venv /py \
    && /py/bin/pip install --upgrade pip

COPY ./requirements.txt /requirements.txt


# Install linux packages, install python dependencies, then remove build dependencies
RUN apk add --no-cache \
    postgresql-client \
    libstdc++ \
    su-exec \
    && apk add --no-cache --virtual .build-deps build-base postgresql-dev musl-dev linux-headers g++ \
    && /py/bin/pip install --no-cache-dir -r /requirements.txt \
    && apk del .build-deps

# copy application code and scripts
COPY ./core /core
COPY ./scripts /scripts

# Create non-root user and required directories
RUN adduser --disabled-password app \
    && mkdir -p /vol/web/static /vol/web/media/pdf \
    && chown -R app:app /vol \
    && chmod -R 755 /vol \
    && chmod -R +x /scripts \
    && chmod +x scripts/entrypoint.sh \
    && chmod +x scripts/run.sh \
    && chown -R app:app /core/logs \
    && chmod 2775 /core/logs

# set work directory
WORKDIR /core
EXPOSE 8000

# The entrypoint script will run as root and then switch to the 'app' user.
ENTRYPOINT ["/scripts/entrypoint.sh"]