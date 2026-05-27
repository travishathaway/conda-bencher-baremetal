#! /bin/bash

source env.sh

podman build --platform linux/amd64 -t registry.bencher.dev/${BENCHER_PROJECT_SLUG}:latest .
