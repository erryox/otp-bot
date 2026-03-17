FROM python:3.10-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh

ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY otp_forwarder.py .

ENV PYTHONUNBUFFERED=1

CMD ["uv", "run", "python", "otp_forwarder.py"]
