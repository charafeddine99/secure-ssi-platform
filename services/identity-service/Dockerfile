FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY tests ./tests
# Private platform-backup directory (WP-28); owned by the service user only.
RUN mkdir -p /var/lib/secure-ssi/backups /var/lib/secure-ssi/ledger-anchor \
    && chown 10001:10001 /var/lib/secure-ssi/backups /var/lib/secure-ssi/ledger-anchor \
    && chmod 700 /var/lib/secure-ssi/backups /var/lib/secure-ssi/ledger-anchor
EXPOSE 8000
USER 10001:10001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
