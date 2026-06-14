FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 appuser

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

RUN pip install --no-cache-dir "python-bidi==0.4.2" --force-reinstall --no-deps && \
    sed -i 's/from bidi import get_display/from bidi.algorithm import get_display/' \
    /usr/local/lib/python3.11/site-packages/easyocr/easyocr.py

COPY --chown=appuser:appuser . .

USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]