# CLI Build Instructions

This document describes how to build and deploy the command-line interface (CLI) tool.

## Building the CLI

To generate a new version of the CLI tool:

1. Execute the build script:
   ```bash
   ./build_and_copy_executable.sh
   ```

This script will:
- Create a Docker container using the provided Dockerfile
- Set up all necessary dependencies
- Build the CLI tool using PyInstaller
- Generate an executable file

The build process uses Docker to ensure a consistent build environment and handle all dependencies automatically.

## Output

The build script will create a new executable in the `dist` directory. The executable name will be formatted as:
polytext-<VERSION>
where `<VERSION>` is the value from the `VERSION` file in the cli directory.

## Deployment

After building, the new executable needs to be uploaded to the following S3 locations:
- `s3://docsity-data-develop/library/`
- `s3://docsity-data/library/`

### Prerequisites

- Docker installed and running
- Appropriate AWS credentials configured for S3 access
- Execute permissions on the build script (`chmod +x build_and_copy_executable.sh`)

### Version Management

The version number is managed through the `VERSION` file in the project root. Update this file before building if you need to create a new version.

## Troubleshooting

If you encounter any issues during the build:
1. Ensure Docker is running
2. Check that you have sufficient permissions
3. Verify that the `VERSION` file exists and contains the correct version number