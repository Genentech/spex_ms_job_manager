#!/usr/bin/env bash

docker build -f ./microservices/ms-job-manager/Dockerfile -t ghcr.io/genentech/spex_ms_job_manager:latest .
docker push ghcr.io/genentech/spex_ms_job_manager:latest

