FROM python:3.12-slim-bookworm
LABEL maintainer="rheumalink-dev"


ENV PYTHONUNBUFFERED=1
ENV PATH="/scripts:/py/bin:$PATH"

# creating venv early
RUN python -m venv /py \
    && /py/bin/pip install --upgrade pip

COPY ./requirements.txt /requirements.txt


# Install linux packages, install python dependencies, then remove build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    libpq-dev \
    build-essential \
    libstdc++6 \
    gosu \
    && /py/bin/pip install --no-cache-dir -r /requirements.txt \
    && rm -rf /var/lib/apt/lists/*

# copy application code and scripts
COPY ./core /core
COPY ./scripts /scripts

# Create non-root user and required directories
# Debian style user creation and permission setup
RUN adduser --disabled-password --no-create-home app \
    && mkdir -p /vol/web/static /vol/web/media/pdf /core/logs \
    && chown -R app:app /vol /core/logs \
    && chmod -R 755 /vol /scripts \
    && chmod +x /scripts/entrypoint.sh \
    && chmod +x /scripts/run.sh \
    && chmod 2775 /core/logs

# set work directory
WORKDIR /core
EXPOSE 8000

# The entrypoint script will run as root and then switch to the 'app' user.
ENTRYPOINT ["/scripts/entrypoint.sh"]