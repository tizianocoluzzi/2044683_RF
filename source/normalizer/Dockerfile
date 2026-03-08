FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py \
     rabbitMQ.py \
     commonTelemetry.py \
     topics.py \
     rest.py \
     actuator.py \
     ./

# ── Upstream service URLs ────────────────────────────────────────────
ENV API_BASE_URL=http://localhost:8080
ENV WS_BASE_URL=ws://localhost:8080
ENV ACTUATOR_ENDPOINT=/api/actuators

# ── RabbitMQ connection ──────────────────────────────────────────────
ENV RABBITMQ_HOST=localhost
ENV RABBITMQ_PORT=5672
ENV RABBITMQ_USER=guest
ENV RABBITMQ_PASSWORD=guest

# ── Polling interval (seconds) ───────────────────────────────────────
ENV SENSOR_POLL_INTERVAL=5

CMD ["python", "app.py"]
