# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y apache2 apache2-dev gcc wget build-essential unrar-free libarchive-dev pkg-config

# Clean up the apt cache to reduce image size
RUN apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip install requests cryptography PyMuPDF flask PyPDF2 werkzeug python-dotenv

# Install mod_wsgi
RUN pip install mod_wsgi

# Install pillow
RUN pip install pillow

# Install Pytz
RUN pip install pytz

# Install pikepdf
RUN pip install pikepdf

# Install pdfrw
RUN pip install pdfrw

# Install psycopg2
RUN pip install psycopg2-binary

# Install libarchive
RUN pip install libarchive-c

# Automatically configure mod_wsgi
#RUN mod_wsgi-express install-module | tee /etc/apache2/mods-available/wsgi.load
#RUN a2enmod wsgi

# Set the working directory in the container
WORKDIR /app

# Copy the Flask application into the container at /app
COPY . /app

# Copy Apache configuration files into place
#COPY signapi.conf /etc/apache2/sites-available/000-default.conf

# Additional Apache configuration
#RUN echo "ServerName localhost" >> /etc/apache2/apache2.conf
#RUN echo "Listen 5000" >> /etc/apache2/ports.conf

# Enable the necessary Apache modules and sites
#RUN a2enmod rewrite
#RUN a2ensite 000-default

# Expose port 5000 on the container
EXPOSE 5000

# Start Apache in the foreground
#CMD ["apache2ctl", "-D", "FOREGROUND"]

# Start mod_wsgi-express with auto-reload
CMD ["mod_wsgi-express", "start-server", "sign.wsgi", "--reload-on-changes", "--user", "www-data", "--group", "www-data", "--port", "5000"]