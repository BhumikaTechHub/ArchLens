FROM python:3.12-slim

WORKDIR /app

# Install Git for repository cloning
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt package.json .

RUN pip install --no-cache-dir -r requirements.txt \
    && npm install --omit=dev --no-audit --no-fund

# Copy project files
COPY . .

# Create directories for persistent data
RUN mkdir -p imported_repositories/repositories \
    imported_repositories/generated \
    imported_repositories/metadata

EXPOSE 8000

CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
