# VERITAS dMRV — backend image
#
# The heavy numerical stack (OpenCV, SciPy, pvlib, astropy) is what makes this
# image large. That is accepted rather than fought: the alternative is a
# multi-stage builder that produces the same artifact for a demo that has to
# come up with one command.
#
# Wheels are built in the builder stage, so the runtime stage carries no
# toolchain. opencv-python-headless and astropy are the two that matter — the
# headless build has no GUI libraries, and it is why there is no libGL.

FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /wheels
COPY backend/requirements.txt .
RUN pip wheel --wheel-dir /wheels -r requirements.txt


FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

# libgl1 and libglib2.0-0 are runtime deps of some OpenCV builds even headless;
# the alternatives are installing a GUI library we do not want, or failing at
# import time with a message that does not say which package is missing.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /wheels /wheels
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-index --find-links=/wheels -r /tmp/requirements.txt \
    && rm -rf /wheels /tmp/requirements.txt

# Run unprivileged. Nothing here needs root, and a demo container is the wrong
# place to hand out one.
RUN useradd --create-home --uid 10001 veritas
WORKDIR /app
COPY --chown=veritas:veritas backend/ /app/
USER veritas

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=40s --retries=5 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

# --host 0.0.0.0, because the default 127.0.0.1 is unreachable from outside the
# container and the symptom is a container that looks healthy but refuses
# connections.
CMD ["uvicorn", "mock_server:app", "--host", "0.0.0.0", "--port", "8000"]
