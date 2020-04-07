FROM python:3.7-slim-buster

COPY requirements.txt /
RUN pip install -r requirements.txt

COPY src /app/src

WORKDIR /app
CMD ["gunicorn","--bind","0.0.0.0:8000","src.app:app"]