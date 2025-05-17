#!/usr/bin/env bash
set -e

docker build . -t yugm2/hr-client-k6:latest
docker push yugm2/hr-client-k6:latest
kind load docker-image yugm2/hr-client-k6:latest
