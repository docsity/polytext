# Use official Python base image
FROM python:3.12-slim

# Set working directory inside container
WORKDIR /app

# Install required system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Core build dependencies and libraries
    build-essential \
    # Dependencies for WeasyPrint and other GUI/graphics libraries
    # GObject and GLib are essential for many of these
    libglib2.0-0 \
    libpango-1.0-0 \
    libharfbuzz0b \
    libffi-dev \
    libcairo2 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    shared-mime-info \
    snapd \
    && rm -rf /var/lib/apt/lists/*

# Copy local requirements folder
COPY ../requirements/ ./requirements/

# Install Python dependencies from specified file
RUN pip install --no-cache-dir --default-timeout=100 -r requirements/default.txt && pip install --no-cache-dir pyinstaller==6.13.0 magika==0.6.2

# Copy remaining application code to working directory
COPY .. .

# Keep container running
CMD ["tail", "-f", "/dev/null"]