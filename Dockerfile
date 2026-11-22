FROM mcr.microsoft.com/playwright/python:v1.51.0-noble
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY tracker.py products.json ./
RUN mkdir -p /app/data && chown -R pwuser:pwuser /app
USER pwuser
ENV PYTHONUNBUFFERED=1
CMD ["python", "tracker.py"]
