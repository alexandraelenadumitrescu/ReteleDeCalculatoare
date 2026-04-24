FROM python:3.11-slim

WORKDIR /app

# Copy all Python sources — one image serves proxy, destination server, and demo client
COPY proxy.py destination_server.py client.py demo_scenarios.py ./

# Pre-create the directories used at runtime
RUN mkdir -p proxy_files server_files

EXPOSE 9000 9001

# Default: run the proxy. Override with `command:` in docker-compose.
CMD ["python", "proxy.py"]
