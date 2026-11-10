FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
# Build the wheel with `uv build` first; runtime package has no dependencies.
COPY dist/*.whl /tmp/
RUN python -m pip install --no-deps --no-cache-dir /tmp/*.whl && rm /tmp/*.whl
COPY configs/dev.toml configs/dev.toml
COPY content/activities.json content/activities.json
USER 10001:10001
ENTRYPOINT ["reachy-companion"]
CMD ["serve"]
