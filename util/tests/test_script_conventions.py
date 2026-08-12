"""Every runnable script in util/ says `#!/usr/bin/env python3`; libraries say
nothing and are not executable, so a shebang marks what can be run.

No script names a specific minor version. It is the ENVIRONMENT's job to put a
Python carrying numpy, scipy, compas, networkx and matplotlib first on PATH --
normally a virtual environment, since Homebrew's Pythons from 3.12 on refuse
`pip install` into their own site-packages (PEP 668), and Homebrew has no formula
for matplotlib, networkx or compas. requirements.txt is the record of what that
environment needs.

Pinning `python3.11` was the previous arrangement, and it worked only because one
particular Homebrew Python happened to have the libraries pip-installed into it.
That is the thing being moved away from: it tied the repo to one machine's
accident, and a venv cannot even supply a `python3.11` command unless it was built
from 3.11.

Worth a test rather than a convention, because getting a shebang wrong fails at
the worst moment. genUniformPolyh.py once claimed `python3` while importing numpy
under the old scheme, so it died with a bare ModuleNotFoundError; genGoldberg.py
had none at all while the docs told you to run it. Both went unnoticed for months,
since anyone who typed an explicit interpreter never saw them.
"""
import os
from pathlib import Path

import pytest

UTIL_DIR = Path(__file__).resolve().parent.parent

EXPECTED_SHEBANG = '#!/usr/bin/env python3'

# Libraries: imported, never run. No shebang, not executable.
LIBRARIES = {'grid_topology.py', 'grid_checks.py', 'polyhedron_shape.py',
             'slisolver.py'}


def scripts():
    return sorted(path for path in UTIL_DIR.glob('*.py'))


def shebang(text):
    first = text.split('\n', 1)[0]
    return first if first.startswith('#!') else None


@pytest.mark.parametrize('path', scripts(), ids=lambda p: p.name)
def test_shebang_is_plain_python3(path):
    line = shebang(path.read_text())

    if path.name in LIBRARIES:
        assert line is None, f'{path.name} is a library; it should have no shebang'
        return

    assert line is not None, (
        f'{path.name} has no shebang, so it cannot be run directly; '
        f'the docs invoke these scripts by path')
    assert line == EXPECTED_SHEBANG, (
        f'{path.name} names {line!r}. Scripts here must not pin a minor version: '
        f'the environment supplies the libraries, and a venv built from a '
        f'different minor version cannot provide that command at all.')


@pytest.mark.parametrize('path', scripts(), ids=lambda p: p.name)
def test_runnable_scripts_are_executable(path):
    """A shebang is no use without the execute bit, and vice versa."""
    executable = os.access(path, os.X_OK)
    if path.name in LIBRARIES:
        assert not executable, f'{path.name} is a library; it should not be +x'
    else:
        assert executable, f'{path.name} needs chmod +x to run by path'


def test_the_libraries_are_the_ones_without_a_main():
    """Keeps LIBRARIES honest: anything with a __main__ block is a command."""
    for path in scripts():
        has_main = "__main__" in path.read_text()
        assert has_main == (path.name not in LIBRARIES), (
            f'{path.name}: __main__ block {"present" if has_main else "absent"}, '
            f'but it is {"listed" if path.name in LIBRARIES else "not listed"} '
            f'as a library')
