# Use Miniconda base image
FROM continuumio/miniconda3:latest

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV CONDA_ENV_NAME=flaskenv

# Set work directory
WORKDIR /app

# Copy environment.yml and create the environment
COPY environment.yml .
RUN conda env create -f environment.yml

# Activate the environment
SHELL ["conda", "run", "-n", "flaskenv", "/bin/bash", "-c"]

# Copy the rest of your app files
COPY . .

# Expose port 80 (required by Azure)
EXPOSE 80

# Use gunicorn as the app server
CMD ["conda", "run", "--no-capture-output", "-n", "flaskenv", "gunicorn", "-b", "0.0.0.0:80", "app:app"]
