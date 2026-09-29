FROM python:3.14-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --create-home workshop && mkdir -p /app/.runtime && chown -R workshop:workshop /app
USER workshop
ENV PORT=8080
EXPOSE 8080
CMD ["sh", "-c", "uvicorn hour_04.api:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1"]
