# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Set environment variables
# PYTHONDONTWRITEBYTECODE 1 prevents Python from writing pyc files to disc
# PYTHONUNBUFFERED 1 ensures that python output is sent straight to terminal (e.g. your container log) without buffering
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install system dependencies (needed for psycopg2 and other libs)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container at /app
COPY requirements.txt /app/

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . /app/

# Expose port 8000
EXPOSE 8000

# Run the command to start the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
