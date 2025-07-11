# Usa un'immagine basata su Debian 11 (Bullseye) per massima compatibilità
FROM python:3.12-slim-bullseye

# Set the working directory inside the container
WORKDIR /app

# Install necessary system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Essential dependencies for builds and some libraries
    build-essential \
    # Dependencies for WeasyPrint and other GUI/graphic libraries
    # GObject and GLib are fundamental for many of these
    libglib2.0-0 \
    libpango-1.0-0 \
    libharfbuzz0b \
    libffi-dev \
    libcairo2 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# Copy your local 'requirements' folder
COPY requirements/ ./requirements/

# Install Python dependencies from the specified file
# This includes core application requirements and developer tools like PyInstaller and Magika.
RUN pip install --no-cache-dir --default-timeout=100 -r requirements/cli.txt && pip install --no-cache-dir  pyinstaller==6.14.1 magika==0.6.2

# Copy the rest of the application code to the working directory
COPY . .

# Keep the container running for development or debugging purposes.
# In production, this might be replaced with the actual application's entry point.
CMD ["tail", "-f", "/dev/null"]