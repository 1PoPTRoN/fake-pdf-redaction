"""Shared pytest fixtures.

The corpus is generated fresh into a temp directory each session so tests are
hermetic and never depend on committed binaries.
"""

import os
import sys

import pytest

_HERE = os.path.dirname(__file__)
sys.path.insert(0, _HERE)  # so `import util` works
sys.path.insert(0, os.path.join(_HERE, "fixtures"))  # so `import gen_fixtures` works

import gen_fixtures  # noqa: E402


@pytest.fixture(scope="session")
def corpus(tmp_path_factory):
    out = tmp_path_factory.mktemp("corpus")
    return gen_fixtures.write_corpus(str(out))


@pytest.fixture(scope="session")
def engine():
    from pdfaudit import Engine

    return Engine()
