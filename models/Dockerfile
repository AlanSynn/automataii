# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Install uv
RUN pip install uv

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
# COPY pyproject.toml /app/

# Install any needed packages specified in pyproject.toml
# Use --system to install globally in the image, adjust if using venv
# Use --no-cache to reduce image size
# RUN uv pip install --system --no-cache --requirement pyproject.toml
RUN pip install openmim

RUN apt-get update && apt-get install -y libgl1-mesa-glx build-essential libglib2.0-0

RUN pip install torch torchvision opencv-python onnxruntime scikit-image

RUN mim install mmdet mmpose mmdeploy mmcv-lite

# Copy the rest of the application code into the container at /app
COPY . /app/src

# Make port 8000 available to the world outside this container (if needed, e.g., for a web app)
# EXPOSE 8000

# Define environment variable
# ENV NAME World

# Run the application command (replace with your actual entry point)
# CMD ["python", "src/automataii/automata_designer.py"]
# Or if you define entry points in pyproject.toml
# CMD ["automataii"]