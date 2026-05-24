# Use official Python image as base
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies + Perforce CLI (p4)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && curl -fSL https://cdist2.perforce.com/perforce/r24.1/bin.linux26x86_64/p4 -o /usr/local/bin/p4 \
    && chmod +x /usr/local/bin/p4 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create necessary directory for Jenkins configs with correct permissions
RUN mkdir -p /app/jenkins && \
    chown -R 1000:1000 /app/jenkins && \
    chmod -R 755 /app/jenkins

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV P4PORT=ssl:sbg-perforce.esl.cisco.com:1666

# Set timezone to IST
ENV TZ=Asia/Kolkata
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Create a non-root user
RUN useradd -m -u 1000 -s /bin/bash appuser && \
    chown -R appuser:appuser /app

# Trust P4 SSL and set up for appuser
USER appuser
RUN p4 -p ssl:sbg-perforce.esl.cisco.com:1666 trust -y || true

# Run the bot
CMD ["python3", "-u", "bot_main.py"]
