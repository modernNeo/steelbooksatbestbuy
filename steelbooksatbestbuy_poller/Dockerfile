FROM python:3.9.13-alpine

WORKDIR /src/steelbooksatbestbuy
COPY steelbooksatbestbuy_website/steelbooksatbestbuy/models.py models.py

WORKDIR /src
COPY steelbooksatbestbuy_poller/settings.py settings.py
COPY steelbooksatbestbuy_poller/dockerized_requirements.txt requirements.txt
COPY steelbooksatbestbuy_dockerized.env steelbooksatbestbuy_dockerized.env
COPY steelbooksatbestbuy_poller/bestbuy_poller.py bestbuy_poller.py
COPY CI/wait-for-postgres.sh wait-for-postgres.sh
COPY steelbooksatbestbuy_poller/startup.sh startup.sh

RUN apk add postgresql
CMD ["./wait-for-postgres.sh", "./startup.sh"]

#CMD ["sh"]
