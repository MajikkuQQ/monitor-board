FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server ./server

RUN mkdir -p /app/data

EXPOSE 8787

CMD ["python", "-m", "server.main"]
