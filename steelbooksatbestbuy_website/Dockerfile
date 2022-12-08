FROM python:3.9.13-alpine

EXPOSE 8000

WORKDIR /src

COPY steelbooksatbestbuy_website/steelbooksatbestbuy steelbooksatbestbuy
COPY steelbooksatbestbuy_website/steelbooksatbestbuy_website steelbooksatbestbuy_website
COPY steelbooksatbestbuy_website/manage.py manage.py
COPY steelbooksatbestbuy_website/dockerized_requirements.txt requirements.txt
COPY steelbooksatbestbuy_dockerized.env steelbooksatbestbuy_dockerized.env
COPY steelbooksatbestbuy_website/startup.sh startup.sh

RUN apk add postgresql
CMD ["./wait-for-postgres.sh", "./startup.sh"]
#CMD ["sh"]
