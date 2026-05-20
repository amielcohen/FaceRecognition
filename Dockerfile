# Base image with Python 3.10
FROM python:3.10-slim

# Prevent .pyc files and enable unbuffered logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# OpenCV needs these system libraries
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install CPU-only torch first (avoids downloading 2GB GPU version)
RUN pip install --default-timeout=1000 --no-cache-dir \
    torch==2.11.0+cpu \
    torchvision==0.26.0+cpu \
    --extra-index-url https://download.pytorch.org/whl/cpu

# Install remaining dependencies
COPY requirements.txt .
RUN pip install --default-timeout=1000 --no-cache-dir -r requirements.txt

# Copy the rest of the project
COPY . .

# FastAPI runs on port 8000
EXPOSE 8000

# Start the API server, only watch /app and exclude frontend
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "/app", "--reload-exclude", "frontend"]