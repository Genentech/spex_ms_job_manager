#!/usr/bin/env bash

docker build -f ./microservices/ms-job-manager/Dockerfile -t spex.job.manager:latest .
docker tag spex.job.manager:latest ghcr.io/genentech/spex.job.manager:latest
docker push ghcr.io/genentech/spex.job.manager:latest