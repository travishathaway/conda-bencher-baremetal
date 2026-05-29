#! /bin/bash

source env.sh

bencher run \
  --project "$BENCHER_PROJECT_SLUG" \
  --image "BENCHER_PROJECT_SLUG:latest" \
  --adapter python_pytest \
  --file results.json