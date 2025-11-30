FROM python:3.9-slim

WORKDIR /app

# Install system dependencies if needed (e.g. for building python packages)
# RUN apt-get update && apt-get install -y gcc

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Environment variable to indicate running in Docker
ENV IN_DOCKER=true
ENV PYTHONUNBUFFERED=1

# Default command (can be overridden in docker-compose)
CMD ["python", "app.py"]
