FROM python:3.9.13-alpine
RUN apk update && apk add alpine-conf
RUN setup-timezone -z Canada/Pacific

ENV SECRET_KEY=$SECRET_KEY
ENV DISCORD_BOT_TOKEN=$DISCORD_BOT_TOKEN
ENV HTTP_HOST=$HTTP_HOST
ENV WEBSITE_DATABASE_PATH=$WEBSITE_DATABASE_PATH

WORKDIR /src

COPY steelbooksatbestbuy_website/steelbooksatbestbuy steelbooksatbestbuy
COPY steelbooksatbestbuy_website/steelbooksatbestbuy_website steelbooksatbestbuy_website
COPY steelbooksatbestbuy_website/manage.py manage.py
COPY steelbooksatbestbuy_website/dockerized_requirements.txt requirements.txt
COPY steelbooksatbestbuy_dockerized.env steelbooksatbestbuy_dockerized.env

RUN apk update && apk add gcc

RUN apk update && apk add musl-dev

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

#CMD ["sh"]
