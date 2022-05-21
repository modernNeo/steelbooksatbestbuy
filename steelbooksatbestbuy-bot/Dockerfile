FROM python:3.9.13-alpine
RUN apk update && apk add alpine-conf
RUN setup-timezone -z Canada/Pacific

ARG SECRET_KEY
ENV SECRET_KEY=SECRET_KEY

WORKDIR /src/steelbooksatbestbuy
COPY steelbooksatbestbuy_website/steelbooksatbestbuy/models.py models.py

WORKDIR /src
COPY steelbooksatbestbuy-bot/bestbuy_bot.py bestbuy_bot.py
COPY steelbooksatbestbuy-bot/settings.py settings.py
COPY steelbooksatbestbuy-bot/dockerized_requirements.txt requirements.txt
COPY steelbooksatbestbuy_dockerized.env steelbooksatbestbuy_dockerized.env

RUN apk update && apk add gcc

RUN apk update && apk add musl-dev

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "bestbuy_bot.py"]

#CMD ["sh"]
