# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y apache2 apache2-dev gcc wget build-essential unrar-free libarchive-dev pkg-config tzdata

# Set the timezone to GMT-3
RUN ln -fs /usr/share/zoneinfo/America/Argentina/Tucuman /etc/localtime && dpkg-reconfigure -f noninteractive tzdata

# Clean up the apt cache to reduce image size
RUN apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip install requests cryptography PyMuPDF flask PyPDF2 werkzeug python-dotenv

# Install mod_wsgi
RUN pip install mod_wsgi

# Install pillow
RUN pip install pillow

# Install pikepdf
RUN pip install pikepdf

# Install pdfrw
RUN pip install pdfrw

# Install psycopg2
RUN pip install psycopg2-binary

# Install libarchive
RUN pip install libarchive-c

# Install reportlab
RUN pip install reportlab

# Automatically configure mod_wsgi
#RUN mod_wsgi-express install-module | tee /etc/apache2/mods-available/wsgi.load
#RUN a2enmod wsgi

# Set the working directory in the container
WORKDIR /app

# Create necessary directories
RUN mkdir -p /app/assets/images \
    && mkdir -p /app/certs/own

# Copy the application code (from the context which is firmar_python/app)
COPY . .

# Make sure all directories have correct permissions
RUN chown -R www-data:www-data /app \
    && chmod -R 755 /app \
    && chmod 600 /app/certs/own/TC_clave_csr.key  # Restrict private key permissions

# Update mod_wsgi configuration for larger file uploads
RUN sed -i "s/default=10485760,/default=1048576000,/" /usr/local/lib/python3.12/site-packages/mod_wsgi/server/__init__.py

# Create necessary directories
RUN mkdir -p /var/documentos_firmados /var/documentos

# Set permissions
RUN chown -R www-data:www-data /app
RUN chmod -R 755 /app

EXPOSE 5000

# Start mod_wsgi-express with the correct path (updated path)
CMD ["mod_wsgi-express", "start-server", "/app/config/sign.wsgi", "--reload-on-changes", "--user", "www-data", "--group", "www-data", "--port", "5000"