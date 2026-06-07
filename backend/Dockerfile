FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Run as non-privileged user for sandbox escape safety
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

# Expose port (Railway defaults to PORT env var, fallback to 8080)
ENV PORT=8080

EXPOSE 8080

# Railway uses $PORT, local uses 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
