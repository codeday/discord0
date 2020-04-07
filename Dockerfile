FROM python:3.7-slim-buster

COPY requirements.txt /
RUN pip install -r requirements.txt

COPY src /app/src

WORKDIR /app
EXPOSE 8000
COPY docker-entrypoint.sh /docker-entrypoint.sh
ENTRYPOINT ["/docker-entrypoint.sh"]