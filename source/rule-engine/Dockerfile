FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app ./app

# Expose FastAPI port
EXPOSE 8000

# Environment (puoi cambiare l'URL degli actuators se serve)
ENV ACTUATOR_BASE_URL=http://host.docker.internal:8080/api/actuators

# Start the service
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
