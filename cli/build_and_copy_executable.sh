#!/bin/bash

# Exit on error
set -e

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Read version from VERSION file in cli directory
if [ ! -f "$SCRIPT_DIR/VERSION" ]; then
    echo "Error: VERSION file not found in cli directory"
    exit 1
fi
VERSION=$(cat "$SCRIPT_DIR/VERSION")

# Color output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting build process for version ${VERSION}${NC}"

# Build Docker image
echo -e "\n${GREEN}Building Docker image...${NC}"
docker build -t polytext-builder -f "$SCRIPT_DIR/Dockerfile" "$PROJECT_ROOT"

# Create temporary container
echo -e "\n${GREEN}Creating and starting Docker container...${NC}"
CONTAINER_ID=$(docker create --name polytext-build-temp polytext-builder)
docker start polytext-build-temp

# Install the package in development mode in the container
echo -e "\n${GREEN}Installing polytext package in development mode...${NC}"
docker exec polytext-build-temp bash -c "cd /app && pip install -e ."

# Verify the installation
echo -e "\n${GREEN}Verifying polytext installation...${NC}"
docker exec polytext-build-temp bash -c "python -c 'import polytext; print(\"Polytext successfully imported\")'"

# Build Python executable with additional configuration
echo -e "\n${GREEN}Building Python executable...${NC}"
docker exec polytext-build-temp bash -c "cd /app/cli && python -m PyInstaller --clean --onefile --name polytext-temp --paths /app --hidden-import=polytext --hidden-import=polytext.loader --hidden-import=polytext.loader.html __main__.py"

# Create output directory if it doesn't exist
mkdir -p "$SCRIPT_DIR/dist"

# Copy executable from container
echo -e "\n${GREEN}Copying executable from container...${NC}"
docker cp polytext-build-temp:/app/cli/dist/polytext-temp "$SCRIPT_DIR/dist/polytext-$VERSION"

# Make the file executable
chmod +x "$SCRIPT_DIR/dist/polytext-$VERSION"

# Cleanup
echo -e "\n${GREEN}Cleaning up...${NC}"
docker stop polytext-build-temp
docker rm polytext-build-temp

echo -e "\n${GREEN}Build completed successfully!${NC}"
echo -e "Executable created at: ${GREEN}$SCRIPT_DIR/dist/polytext-$VERSION${NC}"

# Show file info
echo -e "\nFile information:"
ls -lh "$SCRIPT_DIR/dist/polytext-$VERSION"