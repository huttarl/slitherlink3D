"""Repo-level pytest configuration.

Tests marked 'slow' (see pytest.ini for the marker registry) are skipped
in default runs. To include them:

    pytest --all util/tests      # run everything, fast and slow
    pytest -m slow util/tests    # run only the slow tests

(This hook must live in a conftest.py at the rootdir -- pytest ignores
pytest_addoption in deeper conftest files, such as util/tests/conftest.py.)
"""
import pytest


def pytest_addoption(parser):
    parser.addoption("--all", action="store_true", default=False,
                     help="run all tests, including those marked 'slow'")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--all"):
        return  # Run everything.
    if config.getoption("-m"):
        # The user gave an explicit marker expression (e.g. -m slow);
        # let it govern selection instead of skipping anything.
        return
    skip_slow = pytest.mark.skip(reason="slow test: use --all (or -m slow) to run")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)
