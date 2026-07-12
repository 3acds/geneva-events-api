FROM python:3.12.2-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r api/requirements.txt

EXPOSE 10000

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-10000} api.app:app"]
