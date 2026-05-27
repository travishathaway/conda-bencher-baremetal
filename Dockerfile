# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# conda-bencher-baremetal benchmark image
#
# Strategy: ubuntu:latest base, install pixi, then `pixi install --locked`
# to materialise the exact linux-64 environment from pixi.lock.  The
# conda-mock-server package bundles a pre-built conda channel so no network
# access is required at benchmark runtime.
# ---------------------------------------------------------------------------
FROM ubuntu:latest

# Install minimal system prerequisites
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install pixi (latest)
RUN curl -fsSL https://pixi.sh/install.sh | bash
ENV PATH="/root/.pixi/bin:$PATH"

WORKDIR /workspace

# Copy dependency manifest and lockfile first so Docker can cache the
# expensive `pixi install` layer independently of source changes.
COPY pixi.toml pixi.lock ./

# Install the fully-pinned linux-64 environment from the lockfile.
# --locked ensures the exact versions from pixi.lock are used.
RUN pixi install --locked

# Copy project metadata and test sources
COPY pyproject.toml ./
COPY tests/ ./tests/

# Ensure the results directory exists; the bench task writes JSON here.
RUN mkdir -p /results

# Disable cuda detection
ENV CONDA_OVERRIDE_CUDA=0

# The conda-mock-server package writes CONDA_MOCK_SERVER_ROOT_DIR into
# etc/conda/env_vars.d/ with an absolute path baked at install time on the
# build machine.  Override it here with the correct in-container path so the
# fixture can always locate the bundled channel data.
ENV CONDA_MOCK_SERVER_ROOT_DIR=/workspace/.pixi/envs/default/local/share/conda-mock-server

# Run benchmarks via pixi so the correct conda environment is activated.
# The `bench` task expands to:
#   pytest --benchmark-json /results/results.json tests/
ENTRYPOINT ["pixi", "run", "bench"]
