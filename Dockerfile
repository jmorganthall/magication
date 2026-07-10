# syntax=docker/dockerfile:1

# ── builder ─────────────────────────────────────────────────────────────────
# Build a wheel so the runtime image carries only the installed package, no
# build toolchain. setuptools-scm resolves to `fallback_version` here (the .git
# dir is not in the build context); real versions come from CI, not the image.
FROM python:3.12-slim AS builder
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /src
COPY pyproject.toml ./
COPY src ./src
RUN pip install build && python -m build --wheel --outdir /dist

# ── runtime ─────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
# Run as a non-root user.
RUN useradd --create-home --uid 10001 moat
WORKDIR /app
COPY --from=builder /dist/*.whl /tmp/
RUN pip install /tmp/*.whl && rm -f /tmp/*.whl
USER moat

# The scheduler blocks; a healthcheck confirms the process is alive.
HEALTHCHECK --interval=60s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import moat" || exit 1

CMD ["moat-poll"]
