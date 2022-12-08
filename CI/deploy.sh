#!/bin/bash

# PURPOSE: used be jenkins to launch Wall_e to the CSSS PROD Discord Guild

set -e -o xtrace
# https://stackoverflow.com/a/5750463/7734535

export COMPOSE_PROJECT_NAME="steelbooksbestbuy"



export prod_website_container_name="${COMPOSE_PROJECT_NAME}_website"
export prod_poller_container_name="${COMPOSE_PROJECT_NAME}_poller"
export prod_container_db_name="${COMPOSE_PROJECT_NAME}_db"
export docker_compose_file="CI/docker-compose.yml"
export prod_website_image_name_lower_case=$(echo "${prod_website_container_name}" | awk '{print tolower($0)}')
export prod_poller_image_name_lower_case=$(echo "${prod_poller_container_name}" | awk '{print tolower($0)}')

docker rm -f ${prod_website_container_name} || true
docker rm -f ${prod_poller_container_name} || true
docker image rm -f $(docker images  | grep -i "${prod_website_image_name_lower_case}" | awk '{print $3}') || true
docker image rm -f $(docker images  | grep -i "${prod_poller_image_name_lower_case}" | awk '{print $3}') || true

export SECRET_KEY="${CINEPLEX_SECRET_KEY}";
export HTTP_HOST="steelbooksbestbuy.modernneo.com";

if [ "${JENKINS}" == "true" ]; then
  docker-compose -f "${docker_compose_file}" up -d
else
  docker compose -f "${docker_compose_file}" up -d
fi

sleep 20

website_container_failed=$(docker ps -a -f name=${prod_website_container_name} --format "{{.Status}}" | head -1)
poller_container_failed=$(docker ps -a -f name=${prod_poller_container_name} --format "{{.Status}}" | head -1)
container_db_failed=$(docker ps -a -f name=${prod_container_db_name} --format "{{.Status}}" | head -1)

if [[ "${website_container_failed}" != *"Up"* ]]; then
    docker logs ${prod_website_container_name}
    exit 1
fi

if [[ "${poller_container_failed}" != *"Up"* ]]; then
    docker logs ${prod_poller_container_name}
    exit 1
fi

if [[ "${container_db_failed}" != *"Up"* ]]; then
    docker logs ${prod_container_db_name}
    exit 1
fi
