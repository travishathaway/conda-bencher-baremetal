from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from conda.testing.fixtures import CondaCLIFixture, PathFactoryFixture

pytest_plugins = "conda.testing.fixtures"


def test_benchmark_conda_create(
    benchmark: pytest.fixture,
    conda_cli: CondaCLIFixture,
    path_factory: PathFactoryFixture,
    conda_channel: str,
) -> None:
    """Benchmark: create a new environment with Python from the mock channel.

    A fresh unique prefix is generated for every benchmark round via
    ``path_factory``, ensuring each measurement reflects a cold-start install
    into an empty, non-existent prefix.
    """

    def run() -> None:
        prefix = path_factory()
        out, err, code = conda_cli(
            "create",
            "--prefix", prefix,
            "--channel", conda_channel,
            "--override-channels",
            "--yes",
            "python",
        )
        assert not code, (
            f"conda create failed (exit {code}):\nstdout: {out}\nstderr: {err}"
        )

    benchmark(run)


def test_benchmark_conda_install(
    benchmark: pytest.fixture,
    conda_cli: CondaCLIFixture,
    path_factory: PathFactoryFixture,
    conda_channel: str,
) -> None:
    """Benchmark: install Python into a fresh empty environment.

    For every benchmark round a new empty environment is created first, then
    Python is installed into it from the mock channel.  This ensures each
    measurement is a genuine cold install rather than a no-op update.

    Both the empty-env creation and the install are included inside ``run()``
    so that each round starts from the same clean state.  The empty ``create``
    is intentionally cheap compared to the full solve+install, so its overhead
    is negligible relative to what we are trying to measure.
    """

    def run() -> None:
        prefix = path_factory()

        # Step 1: create an empty environment (fast, no packages)
        out, err, code = conda_cli(
            "create",
            "--prefix", prefix,
            "--yes",
        )
        assert not code, (
            f"conda create (empty) failed (exit {code}):\nstderr: {err}"
        )

        # Step 2: install Python from the offline mock channel into that env
        out, err, code = conda_cli(
            "install",
            "--prefix", prefix,
            "--channel", conda_channel,
            "--override-channels",
            "--yes",
            "python",
        )
        assert not code, (
            f"conda install failed (exit {code}):\nstdout: {out}\nstderr: {err}"
        )

    benchmark(run)
