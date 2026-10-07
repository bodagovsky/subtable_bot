FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src

# ECS supplies PORT=8080 for the two public HTTP services. The worker ignores it.
ENV PORT=8080

CMD ["python", "src/bot.py"]
