#! /bin/bash

source env.sh
echo podman push registry.bencher.dev/${BENCHER_PROJECT_SLUG}:latest
podman push registry.bencher.dev/${BENCHER_PROJECT_SLUG}:latest
# docker push registry.bencher.dev/travishathaway:latest
