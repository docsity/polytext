FROM ubuntu:24.04

# Set the working directory inside the container
WORKDIR /app

# Install necessary system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.12 \
    python3.12-dev \
    python3-pip \
    # Essential dependencies for builds and some libraries
    build-essential \
    # Multimedia framework required by ffmpeg-python and pydub
    ffmpeg \
    # Dependencies for WeasyPrint and other GUI/graphic libraries
    weasyprint \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    # dependencies for convert documents to pdf
    libreoffice \
    # Clean up apt cache to reduce image size
    && rm -rf /var/lib/apt/lists/*

# Copy your local 'requirements' folder
COPY requirements/ ./requirements/

# Install Python dependencies from the specified file
# This includes core application requirements and developer tools like PyInstaller and Magika.
RUN pip3 install --no-cache-dir --default-timeout=100 -r requirements/cli.txt pyinstaller==6.14.1 magika==0.6.2 --break-system-packages

# Copy the rest of the application code to the working directory
COPY . .

# Keep the container running for development or debugging purposes.
# In production, this might be replaced with the actual application's entry point.
CMD ["tail", "-f", "/dev/null"]