FROM python:3.12-slim AS build
WORKDIR /build
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080
RUN groupadd --gid 10001 fleetfix && useradd --uid 10001 --gid 10001 --create-home fleetfix
WORKDIR /app
COPY --from=build /install /usr/local
COPY --chown=fleetfix:fleetfix app ./app
COPY --chown=fleetfix:fleetfix static ./static
USER 10001:10001
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]
