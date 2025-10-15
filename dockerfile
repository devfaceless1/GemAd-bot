FROM python:3.11-slim

RUN apt-get update && apt-get install -y build-essential libffi-dev libssl-dev && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir fastapi==0.115.0 uvicorn==0.25.0 aiogram==3.2.0 motor==3.7.1 pymongo==4.9.1 python-dotenv==1.0.0

COPY . .

ENV PORT=10000

CMD ["uvicorn", "bot:app", "--host", "0.0.0.0", "--port", "10000"]
