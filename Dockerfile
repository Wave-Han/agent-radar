FROM python:3.13-slim

WORKDIR /app

# Install dependencies first (leverages Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY agent_radar/ agent_radar/
COPY docs_kb/ docs_kb/
# NOTE: .env is NOT copied into the image (secrets stay out).
# Use docker-compose env_file or runtime env vars instead.

# Bind to all interfaces inside the container
ENV AGENT_RADAR_HOST=0.0.0.0
ENV AGENT_RADAR_PORT=8000

# Persistent data: SQLite DB lives here (mount as volume)
VOLUME ["/app/data"]

# Health check: hit the web UI
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/')" || exit 1

EXPOSE 8000

CMD ["python", "-m", "agent_radar.web"]
