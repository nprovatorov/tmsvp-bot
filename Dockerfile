FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN pip install --no-cache-dir clamd
COPY . .
CMD ["python", "-m", "bot"]
