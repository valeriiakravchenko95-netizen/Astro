import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astro.ephemeris import load_ephemeris  # noqa: E402


@pytest.fixture(scope="session")
def eph():
    return load_ephemeris()


@pytest.fixture(scope="session")
def ts(eph):
    return eph.ts
