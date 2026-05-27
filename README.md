# conda-bencher-baremetal

Integration benchmarks for [conda](https://github.com/conda/conda) using [Bencher](https://bencher.dev) bare metal runners.

## Overview

This repository measures the real-world performance of two core conda operations:

- **`conda create`** — time to create a new environment with Python from scratch
- **`conda install`** — time to install Python into a freshly created empty environment

Benchmarks run against a fully offline local conda channel served by [conda-mock-server](https://github.com/travishathaway/conda-mock-server). This eliminates network variability so every measurement reflects only conda's own solver and installation logic.

Results are tracked over time on [Bencher](https://bencher.dev), which detects performance regressions before they merge. The bare metal runners used by Bencher provide dedicated hardware with no shared-tenant noise, giving more accurate and reproducible timings than typical CI VMs.

## How it works

```
┌─────────────────────────────────────────────────────────┐
│  pytest session                                          │
│                                                          │
│  conda_channel fixture (session scope)                   │
│  └─ starts `cms serve` pointing at the bundled channel   │
│     (CONDA_MOCK_SERVER_ROOT_DIR, set on env activation)  │
│     OS assigns a free port; no outbound network needed   │
│                                                          │
│  test_benchmark_conda_create                             │
│  └─ benchmark loop: conda create --prefix <fresh> python │
│                                                          │
│  test_benchmark_conda_install                            │
│  └─ benchmark loop: conda create (empty)                 │
│                      conda install python                │
└─────────────────────────────────────────────────────────┘
```

Each benchmark round receives a unique, non-existent prefix from pytest's `path_factory` fixture so every measurement is a genuine cold install. Results are written to `/results/results.json` in [pytest-benchmark JSON format](https://pytest-benchmark.readthedocs.io/en/latest/usage.html#commandline-options), which Bencher consumes via its `python_pytest` adapter.

## Project structure

```
.
├── Dockerfile                          # Self-contained benchmark image (ubuntu + pixi)
├── pixi.toml                           # Workspace config: deps, platforms, tasks
├── pixi.lock                           # Fully-pinned lockfile (osx-arm64, linux-64)
├── pyproject.toml                      # pytest configuration
├── tests/
│   ├── conftest.py                     # conda_channel fixture (starts cms serve)
│   └── test_benchmarks.py             # benchmark tests
└── .github/workflows/
    ├── base_benchmarks.yml             # push to main → build image → run on bare metal
    ├── pr_benchmarks.yml               # PR opened/updated → run on bare metal
    └── pr_benchmarks_closed.yml        # PR closed → archive Bencher branch data
```

## Prerequisites

- [pixi](https://pixi.sh) — manages the conda environment and project tasks
- [Docker](https://docs.docker.com/engine/install/) — required to build and push the benchmark image
- A [Bencher](https://bencher.dev) account (free tier is sufficient to get started)

## Local setup

### 1. Install pixi

```bash
curl -fsSL https://pixi.sh/install.sh | bash
```

### 2. Install the project environment

```bash
pixi install
```

This reads `pixi.lock` and installs the fully-pinned environment including conda, conda-mock-server, pytest, and pytest-benchmark. On first run it may take a few minutes to download packages.

### 3. Activate the environment

```bash
pixi shell
```

Activating the environment sets `CONDA_MOCK_SERVER_ROOT_DIR` to the bundled channel data that ships inside the conda-mock-server package. The benchmark fixtures depend on this variable.

## Running benchmarks locally

### Run once (no benchmark statistics)

```bash
pixi run test
```

This runs pytest without benchmark timing — useful for verifying that the tests pass before committing.

### Run with benchmarking

```bash
mkdir -p results
RESULTS_DIR=$PWD/results pixi run bench
```

> **Note:** The `bench` task writes results to `/results/results.json` (the path used inside the Docker container). Override this by editing `pixi.toml` or passing pytest flags directly:
>
> ```bash
> pixi run -- pytest --benchmark-json results/results.json tests/
> ```

Benchmark output looks like:

```
--------------------------------------------------------------------------- benchmark: 2 tests ---------------------------------------------------------------------------
Name (time in s)                  Min     Max    Mean  StdDev  Median    IQR  Outliers  OPS  Rounds  Iterations
--------------------------------------------------------------------------------------------------------------------------------------------------------------------------
test_benchmark_conda_create     1.234   1.456   1.312   0.054   1.298  0.071       1;0  0.76       5           1
test_benchmark_conda_install    1.189   1.401   1.267   0.048   1.251  0.063       1;0  0.79       5           1
--------------------------------------------------------------------------------------------------------------------------------------------------------------------------
```

## Bencher setup (one-time)

Before the GitHub Actions workflows can push results to Bencher, complete the following steps once.

### 1. Create a Bencher project

Install the [Bencher CLI](https://bencher.dev/docs/how-to/install-cli/) and run:

```bash
bencher run "bencher mock --count 0"
```

The output contains a `View report` URL. Your **project slug** is the path segment after `/perf/` — for example if the URL is:

```
https://bencher.dev/perf/my-conda-benchmarks-abc1234/reports/...
```

then your project slug is `my-conda-benchmarks-abc1234`.

Claim the project by following the `Claim this project` link in the output.

### 2. Create an API token

Navigate to the newly created project and create a key underneath this project (e.g. `https://bencher.dev/console/projects/<project-slug>/keys/`). This is what you use as the `BENCHER_API_KEY` later.

### 3. Add GitHub repository secrets and variables

In your GitHub repository go to **Settings → Secrets and variables → Actions** and add:

| Type | Name | Value |
|------|------|-------|
| Secret | `BENCHER_API_KEY` | Your Bencher API token |
| Variable | `BENCHER_PROJECT_SLUG` | Your project slug (e.g. `my-conda-benchmarks-abc1234`) |

### 4. Push the benchmark image manually and test it (first time)

The GitHub Actions workflow builds and pushes the image automatically on every `main` push. To push it manually for the first time:

```bash
cp env.sh.template env.sh
```

Update `env.sh` with your `BENCHER_API_KEY` and `BENCHER_PROJECT_SLUG` and run:

```bash
source env.sh
```

After that, use `podman` to login to the Bencher container registry:

```bash
# Log in to the Bencher OCI registry
echo $BENCHER_API_KEY | docker login registry.bencher.dev -u $BENCHER_PROJECT_SLUG --password-stdin

# Build the image (requires Docker with linux/amd64 support)
pixi run build-image

# Push it
pixi run push-image
```

You can test it with the following command:

```bash
bencher run --project $BENCHER_PROJECT_SLUG --image $BENCHER_PROJECT_SLUG:latest
```

## GitHub Actions workflows

Three workflows are included:

### `base_benchmarks.yml` — tracks `main`

Triggered on every push to `main`. Builds the benchmark image, pushes it to the Bencher OCI registry, then runs the benchmarks on dedicated bare metal hardware. A statistical threshold (Student's t-test, upper boundary p=0.99, sample size 64) is applied to detect regressions automatically.

### `pr_benchmarks.yml` — tracks pull requests

Triggered when a PR is opened, updated, or edited (same-repo branches only — not forks). Builds and pushes the image, then runs benchmarks on bare metal. Results are compared against the base branch. Bencher posts a comment on the PR with the benchmark results and flags any regressions.

### `pr_benchmarks_closed.yml` — cleans up closed PRs

Triggered when a PR is closed. Archives the PR's Bencher branch data to keep the project dashboard tidy.

## Adding more benchmarks

Add new test functions to `tests/test_benchmarks.py` following the existing pattern:

```python
def test_benchmark_conda_search(
    benchmark: pytest.fixture,
    conda_cli: CondaCLIFixture,
    conda_channel: str,
) -> None:
    def run() -> None:
        out, err, code = conda_cli(
            "search",
            "--channel", conda_channel,
            "--override-channels",
            "python",
        )
        assert not code

    benchmark(run)
```

No changes to `conftest.py`, `pixi.toml`, or the Dockerfile are needed — the new test is picked up automatically.

## Extending the mock channel

The bundled channel in conda-mock-server ships with Python and its dependencies. To add more packages (e.g. numpy, pandas) to the offline channel, use the `cms` CLI:

```bash
# Add a dependency group
cms add numpy --platform linux-64 --platform osx-arm64

# Download and index the resolved packages
cms download

# The channel is now available at $CONDA_MOCK_SERVER_ROOT_DIR
```

See the [conda-mock-server documentation](https://github.com/travishathaway/conda-mock-server#getting-started) for full details.
