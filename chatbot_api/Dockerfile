FROM python:3.11-slim

# install netcat for waiting on Neo4j
RUN apt-get update && apt-get install -y netcat-openbsd && apt-get clean

WORKDIR /app

# Copy source and dependency files
COPY src/ /app/src
COPY src/scripts /app/scripts           
COPY pyproject.toml /code/pyproject.toml
RUN pip install /code/.

# Set the PYTHONPATH to include the /app/src directory
ENV PYTHONPATH=/app/src

# Copy entrypoint.sh to the container
COPY src/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

CMD ["sh", "/app/entrypoint.sh"]
