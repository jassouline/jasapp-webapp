FROM python:3.11

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt \
    && addgroup jasapp \
    && useradd -rm -d /home/jasapp -s /bin/bash -g jasapp -u 1001 jasapp \
    && chmod +x /app/healthcheck.py

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD python /app/healthcheck.py || exit 1

EXPOSE 8000

USER jasapp

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]