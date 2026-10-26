FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Default command (the worker overrides this in compose)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
