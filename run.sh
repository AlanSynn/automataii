#!/bin/bash
set -e

# Define the image name
IMAGE_NAME="automataii-dev"

# Build the Docker image if it doesn't exist or if Dockerfile has changed
# (A more robust check might compare timestamps or use build args)
docker build -t $IMAGE_NAME .

# Run the container
# Mount the source code for live updates
# Mount a volume for the virtual environment to persist installs
docker run --rm -it \
    -v "$(pwd)/src:/app/src" \
    -v "automataii_venv:/app/.venv" \
    $IMAGE_NAME "$@"

# If no command is provided, default to running the main script (adjust as needed)
if [ $# -eq 0 ]; then
    # Example: run the main Python module
    docker run --rm -it \
        -v "$(pwd)/src:/app/src" \
        -v "automataii_venv:/app/.venv" \
        $IMAGE_NAME python -m automataii.automata_designer
fi