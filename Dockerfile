# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Install ffmpeg and other dependencies
RUN apt-get update && apt-get install ffmpeg libsm6 libxext6  -y

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the requirements file into the container at /usr/src/app
COPY requirements.txt optional-requirements.txt ./

# Run pip to install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install the optional dependencies
RUN pip install --no-cache-dir -r optional-requirements.txt

# Copy the source code into the container
COPY . .

# Command to run the application
CMD ["python", "app/main.py"]
