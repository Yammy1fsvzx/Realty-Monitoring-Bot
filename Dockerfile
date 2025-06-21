FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ .

VOLUME ["/app/data", "/app/reports"]

CMD ["python", "main.py"] 