FROM python:3.11-alpine

# Install poetry in its own venv
# https://python-poetry.org/docs/#installing-manually
ENV POETRY_CACHE_DIR /opt/poetry/cache
ENV POETRY_VENV /opt/poetry/venv
WORKDIR ${POETRY_VENV}
RUN python3 -m venv ${POETRY_VENV}
RUN ${POETRY_VENV}/bin/pip install -U pip setuptools
RUN ${POETRY_VENV}/bin/pip install poetry
RUN ln -s ${POETRY_VENV}/bin/poetry /bin/poetry

RUN addgroup -S relay && adduser -S relay -G relay

# Create and activate venv
ENV VIRTUAL_ENV /venv
WORKDIR $VIRTUAL_ENV
RUN python -m venv $VIRTUAL_ENV
ENV PATH "$VIRTUAL_ENV/bin:$PATH"

WORKDIR /opt/grafana-matrix-alerting
COPY relay/pyproject.toml .
COPY relay/poetry.lock .
RUN poetry install --without dev --with ecs --compile

COPY relay /opt/grafana-matrix-alerting
RUN poetry install --without dev --with ecs --compile

USER relay

# Binding to localhost makes little sense in the container
ENV RELAY_HOST 0.0.0.0

CMD python -m grafana_matrix_alerting
