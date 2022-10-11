FROM python:3.10-slim

RUN pip install --no-cache-dir --upgrade pip

WORKDIR /

COPY . /app/
RUN ls /app;pip install --no-cache-dir -r /app/requirements.txt

CMD ["python", "/app/app.py"]
