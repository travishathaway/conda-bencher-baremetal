from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Generator

import pytest

pytest_plugins = "conda.testing.fixtures"

if TYPE_CHECKING:
    pass


def _find_channel_root() -> Path | None:
    """Return the conda-mock-server channel root, or None if not found.

    Tries, in order:
    1. CONDA_MOCK_SERVER_ROOT_DIR env var (set by conda env activation or
       overridden explicitly in the Docker image ENV).
    2. Derive from the installed conda_mock_server package location — works
       even when the env var was baked with the wrong absolute path at build
       time (e.g. the developer's machine path leaked into the image).
    """
    root_dir = os.environ.get("CONDA_MOCK_SERVER_ROOT_DIR")
    if root_dir:
        p = Path(root_dir)
        if p.is_dir():
            return p

    # Fallback: locate the data directory relative to the installed package.
    # The package always installs channel data at:
    #   <conda_prefix>/local/share/conda-mock-server/
    # conda_mock_server.__file__ is at:
    #   <conda_prefix>/lib/pythonX.Y/site-packages/conda_mock_server/__init__.py
    try:
        import conda_mock_server
        pkg_path = Path(conda_mock_server.__file__).resolve()
        # Walk up: __init__.py -> conda_mock_server/ -> site-packages/
        #          -> lib/ -> pythonX.Y/ -> <conda_prefix>
        conda_prefix = pkg_path.parents[4]
        candidate = conda_prefix / "local" / "share" / "conda-mock-server"
        if candidate.is_dir():
            return candidate
    except Exception:
        pass

    return None


@pytest.fixture(scope="session")
def conda_channel() -> Generator[str, None, None]:
    """Expose the pre-built bundled channel as a local file:// URL.

    Uses conda's native support for local directory channels, bypassing all
    network access.  This works in sandboxed environments (e.g. Firecracker
    microVMs) where TCP — including loopback — is unavailable.

    The conda-mock-server conda package bundles channel data at
    ``<conda_prefix>/local/share/conda-mock-server/``.  The channel root is
    located via CONDA_MOCK_SERVER_ROOT_DIR (set by env activation or the
    Dockerfile ENV) with a fallback that derives the path from the installed
    package location.

    Yields a ``file:///...`` URL pointing at the channel root directory.
    """
    channel_path = _find_channel_root()
    if channel_path is None:
        pytest.skip(
            "conda-mock-server channel data not found. "
            "Set CONDA_MOCK_SERVER_ROOT_DIR or activate the pixi/conda environment."
        )

    yield f"file://{channel_path}"
