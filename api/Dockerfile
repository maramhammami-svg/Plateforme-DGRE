FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN useradd --system --no-create-home --uid 1000 appuser && chown -R appuser /app \
    && mkdir -p /data/documents && chown -R appuser /data/documents
USER appuser
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
