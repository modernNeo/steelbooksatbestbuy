FROM python:3.9.13-alpine
RUN apk update && apk add alpine-conf
RUN setup-timezone -z Canada/Pacific

WORKDIR /src/steelbooksatbestbuy
COPY steelbooksatbestbuy_website/steelbooksatbestbuy/models.py models.py

WORKDIR /src
COPY steelbooksatbestbuy_poll_bestbuy/settings.py settings.py
COPY steelbooksatbestbuy_poll_bestbuy/dockerized_requirements.txt requirements.txt
COPY steelbooksatbestbuy_dockerized.env steelbooksatbestbuy_dockerized.env
COPY steelbooksatbestbuy_poll_bestbuy/bestbuy_api.py bestbuy_api.py

RUN apk update && apk add gcc

RUN apk update && apk add musl-dev

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "bestbuy_api.py"]

#CMD ["sh"]
