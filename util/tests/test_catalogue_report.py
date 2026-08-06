"""Tests for catalogue_report.py's staleness guard.

The report takes its playable-puzzle counts from data/grids.json, not from the
puzzle files, so a catalogue that hasn't been rebuilt makes the whole report
quietly wrong -- which happened: a regenerated grid kept showing its old count and
that count was then reported as fact. These lock down the warning that catches it.

Only the guard is tested. The rest of the script is presentation, and the figures
it presents are checked by test_data_puzzles.py against the real data.
"""
import io
import os

from catalogue_report import files_newer_than_catalogue, warn_if_stale


def touch(path, when):
    """Create `path` and set its modification time to `when`."""
    path.write_text('{}')
    os.utime(path, (when, when))


def test_no_files_newer_than_the_catalogue(tmp_path):
    touch(tmp_path / 'cube.json', 1000)
    touch(tmp_path / 'cube-puzzles.json', 1000)
    touch(tmp_path / 'grids.json', 2000)
    assert files_newer_than_catalogue(tmp_path) == []
    assert warn_if_stale(tmp_path, out=io.StringIO()) is False


def test_a_newer_puzzle_file_is_reported(tmp_path):
    touch(tmp_path / 'grids.json', 1000)
    touch(tmp_path / 'dtC-puzzles.json', 2000)
    assert files_newer_than_catalogue(tmp_path) == ['dtC-puzzles.json']


def test_a_newly_added_grid_is_reported(tmp_path):
    """A grid added without rebuilding doesn't appear in the report at all, which
    is even quieter than a wrong count."""
    touch(tmp_path / 'grids.json', 1000)
    touch(tmp_path / 'newSolid.json', 2000)
    assert files_newer_than_catalogue(tmp_path) == ['newSolid.json']


def test_the_catalogue_itself_is_never_listed(tmp_path):
    # grids.json is trivially not newer than itself; guard against an
    # off-by-nothing that would make the warning fire always.
    touch(tmp_path / 'grids.json', 1000)
    assert files_newer_than_catalogue(tmp_path) == []


def test_several_stale_files_are_all_listed_sorted(tmp_path):
    touch(tmp_path / 'grids.json', 1000)
    for name in ('dbD-puzzles.json', 'dtC-puzzles.json', 'dtD-puzzles.json'):
        touch(tmp_path / name, 2000)
    assert files_newer_than_catalogue(tmp_path) == [
        'dbD-puzzles.json', 'dtC-puzzles.json', 'dtD-puzzles.json']


def test_missing_catalogue_does_not_raise(tmp_path):
    """No grids.json at all is a different problem, reported elsewhere; this
    guard must not be what crashes."""
    touch(tmp_path / 'cube.json', 1000)
    assert files_newer_than_catalogue(tmp_path) == []
    assert warn_if_stale(tmp_path, out=io.StringIO()) is False


def test_the_warning_says_what_to_do(tmp_path):
    touch(tmp_path / 'grids.json', 1000)
    touch(tmp_path / 'dtC-puzzles.json', 2000)
    out = io.StringIO()
    assert warn_if_stale(tmp_path, out=out) is True
    message = out.getvalue()
    assert 'dtC-puzzles.json' in message
    assert 'build_catalogue.py' in message


def test_the_warning_goes_to_stderr_by_default(tmp_path, capsys):
    """The point of stderr: the report is usually read through a pipe such as
    `| grep dtC`, which would filter a stdout warning out of sight."""
    touch(tmp_path / 'grids.json', 1000)
    touch(tmp_path / 'dtC-puzzles.json', 2000)
    assert warn_if_stale(tmp_path) is True
    captured = capsys.readouterr()
    assert 'build_catalogue.py' in captured.err
    assert captured.out == ''


def test_the_warning_lists_at_most_six_names(tmp_path):
    """A wholesale regeneration shouldn't bury the instruction under 50 names."""
    touch(tmp_path / 'grids.json', 1000)
    for i in range(9):
        touch(tmp_path / f'grid{i}-puzzles.json', 2000)
    out = io.StringIO()
    warn_if_stale(tmp_path, out=out)
    message = out.getvalue()
    assert '9 data file(s)' in message
    assert 'and 3 more' in message
    assert 'build_catalogue.py' in message
