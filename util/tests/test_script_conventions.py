"""Every script in util/ must declare the interpreter it actually needs.

The rule: a file needing numpy, scipy, compas or networkx says `python3.11`, one
that is standard-library only says `python3`, and a library says neither and is not
executable. Worth a test rather than a convention, because getting it wrong fails
at the worst moment -- genUniformPolyh.py claimed `python3` while importing numpy,
so it died with a bare ModuleNotFoundError, and genGoldberg.py had no shebang at
all while the docs told you to run it. Both went unnoticed for months, since anyone
who happened to type an explicit `python3.11` never saw it.
"""
import os
import re
from pathlib import Path

import pytest

UTIL_DIR = Path(__file__).resolve().parent.parent

# Third-party packages that only the 3.11 interpreter here has.
NEEDS_311 = ('numpy', 'scipy', 'compas', 'networkx', 'matplotlib')

# Libraries: imported, never run. No shebang, not executable.
LIBRARIES = {'grid_topology.py', 'grid_checks.py', 'slisolver.py'}


def scripts():
    return sorted(path for path in UTIL_DIR.glob('*.py'))


def imports_third_party(text):
    """The heavy packages a file imports at module level."""
    return {package for package in NEEDS_311
            if re.search(rf'^\s*(?:import {package}|from {package})',
                         text, re.MULTILINE)}


def lends_its_interpreter(text):
    """Whether the script launches another one with `sys.executable`.

    Then its OWN interpreter has to be the capable one, even if it imports nothing
    heavy itself: run_gen.py is standard-library only, but it hands sys.executable
    to genSliPuzzles, which needs compas. Contrast fill_puzzles.py, which runs
    run_gen.py by path and so leaves the choice to run_gen's shebang -- it can stay
    on plain python3.
    """
    return 'sys.executable' in text


def shebang(text):
    first = text.split('\n', 1)[0]
    return first if first.startswith('#!') else None


@pytest.mark.parametrize('path', scripts(), ids=lambda p: p.name)
def test_shebang_matches_what_the_script_imports(path):
    text = path.read_text()
    line = shebang(text)
    heavy = imports_third_party(text)

    if path.name in LIBRARIES:
        assert line is None, f'{path.name} is a library; it should have no shebang'
        return

    assert line is not None, (
        f'{path.name} has no shebang, so it cannot be run directly; '
        f'the docs invoke these scripts by path')
    if heavy:
        assert '3.11' in line, (
            f'{path.name} imports {sorted(heavy)}, so its shebang must name '
            f'python3.11, not {line!r}')
    elif lends_its_interpreter(text):
        assert '3.11' in line, (
            f'{path.name} passes sys.executable to a child that needs the heavy '
            f'packages, so its own shebang must name python3.11, not {line!r}')
    else:
        assert line == '#!/usr/bin/env python3', (
            f'{path.name} is standard-library only, so plain python3 will do; '
            f'got {line!r}')


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
