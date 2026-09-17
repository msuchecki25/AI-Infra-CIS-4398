# RAWBerry API container image
#
# Built for deployment to Google Cloud Run. Cloud Run injects a PORT
# environment variable (default 8080) and expects the container to listen
# on 0.0.0.0:$PORT, so the entrypoint below reads $PORT rather than
# hardcoding a port number.

FROM python:3.12-slim

# Prevent Python from writing .pyc files and buffering stdout/stderr,
# which keeps container logs flowing to Cloud Logging in real time.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

# Install dependencies first so Docker can cache this layer when only
# application code changes.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application source.
COPY app ./app

EXPOSE 8080

# Use shell form so the ${PORT} environment variable (set by Cloud Run at
# runtime) is expanded correctly.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
