FROM python:3.12-slim

LABEL maintainer="SuperInstance"
LABEL description="FLUX Constraint Engine — REST API"
LABEL version="1.0"

WORKDIR /app

# Copy Python source
COPY src/python/flux_constraint.py /app/
COPY src/python/flux_server.py /app/

# Install Flask
RUN pip install --no-cache-dir flask

# Expose port
EXPOSE 8080

# Environment
ENV FLUX_API_KEY=""
ENV FLUX_PORT=8080

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"

# Run
CMD ["python3", "flux_server.py"]
