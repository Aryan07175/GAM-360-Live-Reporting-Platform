FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the server code
COPY mcp_server /app/mcp_server

# The docker-compose file will mount the config folder to /app/config
# so that the credentials can be loaded correctly.

# Expose port
EXPOSE 8000

# Set the working directory to the root of the project
# so that `config/googleads.yaml` resolves correctly.
CMD ["python", "mcp_server/server.py"]
