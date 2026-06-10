# Chess Challenger — production image (Python + Stockfish)
FROM python:3.12-slim

# Stockfish UCI engine. The Debian package installs to /usr/games/stockfish.
RUN apt-get update \
    && apt-get install -y --no-install-recommends stockfish \
    && rm -rf /var/lib/apt/lists/*
ENV STOCKFISH_PATH=/usr/games/stockfish

WORKDIR /app

# Install Python deps first for better layer caching.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Application code.
COPY chess_coach ./chess_coach
COPY webapp ./webapp
COPY data ./data

# Conservative defaults sized for a small (1 vCPU / 512MB) cloud instance.
# Override any of these in your host's environment for a bigger box.
ENV PORT=8000 \
    CC_WORKERS=2 \
    CC_ENGINE_THREADS=1 \
    CC_ENGINE_HASH_MB=32 \
    CC_MAX_CONCURRENT=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000
# Bind to 0.0.0.0 and the platform-provided $PORT.
CMD ["sh", "-c", "uvicorn webapp.server:app --host 0.0.0.0 --port ${PORT:-8000}"]
