# Use Miniconda base image
FROM continuumio/miniconda3:latest

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV CONDA_ENV_NAME=flaskenv

# Set work directory
WORKDIR /app

# Setup pytesseract OCR engine
RUN apt-get update && \
    apt-get install -y tesseract-ocr tesseract-ocr-nld

# Copy environment.yml and create the environment
COPY environment.yml .
RUN conda env create -f environment.yml

# Activate the environment
SHELL ["conda", "run", "-n", "qompare_model_api", "/bin/bash", "-c"]

# Copy the rest of your app files
COPY . .

# Expose port 80 (required by Azure)
EXPOSE 80

# Use gunicorn as the app server
CMD ["conda", "run", "--no-capture-output", "-n", "qompare_model_api", "python", "app.py"]

