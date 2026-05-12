FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright \
    HOST=0.0.0.0 \
    PORT=5001 \
    FLASK_DEBUG=0

# Xvfb gives Chromium a real display; the rest are Chromium's shared-lib
# deps. Playwright fetches the browser binary itself in the next step.
RUN apt-get update && apt-get install -y --no-install-recommends \
        xvfb \
        xauth \
        ca-certificates \
        fonts-liberation \
        libnss3 libnspr4 libdbus-1-3 libxkbcommon0 \
        libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
        libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
        libgbm1 libpango-1.0-0 libcairo2 libasound2 \
        libatspi2.0-0 libx11-xcb1 libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install -r requirements.txt \
    && pip install playwright==1.49.1 \
    && python -m playwright install chromium

COPY . .

EXPOSE 5001

CMD ["python", "app.py"]
