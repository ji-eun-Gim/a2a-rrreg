FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml /app/
COPY app /app/app
RUN pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir -e .

ENV FLASK_APP=app:create_app

EXPOSE 8000
CMD ["gunicorn", "app:create_app()", "-w", "2", "-b", "0.0.0.0:8000"]
