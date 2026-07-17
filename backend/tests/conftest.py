import os
import sys

import pytest

# Ensure backend/ is on sys.path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def fixtures_dir():
    return FIXTURES


@pytest.fixture
def load_gpx():
    def _load(filename):
        with open(os.path.join(FIXTURES, filename)) as f:
            return f.read()
    return _load
