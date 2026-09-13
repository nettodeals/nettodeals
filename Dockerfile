FROM python:3.11-slim

WORKDIR /app

# Systemabhängigkeiten installieren
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Abhängigkeiten kopieren und installieren
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# App-Code kopieren
COPY . .

# Port für FastAPI freigeben
EXPOSE 8000

# Startbefehl
CMD ["uvicorn", "main:app", --host", "0.0.0.0", "--port", "8000"]
