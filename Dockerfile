FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
COPY packages.txt .
RUN apt-get update \
    && ACCEPT_EULA=Y xargs -a packages.txt apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Environment defaults
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STREAMLIT_SERVER_HEADLESS=true

# Start the Streamlit app
CMD ["./start.sh"]
