FROM python:3.11-slim

# Install git for version control feature
RUN apt-get update && apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install dependencies
COPY pyproject.toml README.md ./
COPY src/ src/
RUN pip install --no-cache-dir -e "."

# Copy remaining files
COPY . .

# Configure git for version control
RUN git config --global user.email "pbi-developer@app" && \
    git config --global user.name "PBI Developer"

# Railway sets PORT env var
ENV PORT=8501

EXPOSE ${PORT}

CMD pbi-dev serve --host 0.0.0.0 --port ${PORT}
