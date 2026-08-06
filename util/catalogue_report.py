#!/usr/bin/env python3
"""Report what data/ currently holds: one line per grid, plus totals.

Usage:
    util/catalogue_report.py [stem_or_gridId ...]

With no arguments, every grid in data/grids.json, in catalogue order (which is
progression order: by edges, then faces). With arguments, only the grids whose
file stem or gridId matches -- handy after adding or regenerating one.

Reads data/grids.json for the geometry and playable-puzzle counts, and each
data/<stem>-puzzles.json for the display puzzles, which the catalogue doesn't
track. Reporting only: rebuild the catalogue with util/build_catalogue.py, and
leave the checking to the test suites.

Standard library only, so plain python3 runs it -- no compas or numpy needed.
"""
import json
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / 'data'

# Grids at least this big are the ones the title screen can choose from, so a
# missing display puzzle is worth mentioning for them and not for the rest.
# Mirrors TITLE_SCREEN_MIN_FACES in js/constants.js.
TITLE_SCREEN_MIN_FACES = 11


def display_puzzle_count(stem):
    """How many display-only puzzles a grid's puzzle file holds (0 if none)."""
    path = DATA_DIR / f'{stem}-puzzles.json'
    if not path.exists():
        return 0
    return len(json.loads(path.read_text()).get('displayPuzzles', []))


def main():
    catalogue = json.loads((DATA_DIR / 'grids.json').read_text())
    wanted = sys.argv[1:]
    grids = [g for g in catalogue['grids']
             if not wanted or g['file'] in wanted or g['gridId'] in wanted]
    if not grids:
        print(f'No grid matches {wanted}. Names are file stems or gridIds; '
              f'run with no arguments to list them all.', file=sys.stderr)
        sys.exit(1)

    print(f'{"file":6} {"gridId":7} {"name":42} {"F":>4} {"E":>4} {"V":>4} '
          f'{"puz":>4} {"disp":>4}  categories')
    for g in grids:
        stem = g['file']
        print(f'{stem:6} {g["gridId"]:7} {g["gridName"]:42} '
              f'{g["faces"]:4} {g["edges"]:4} {g["vertices"]:4} '
              f'{g["numPuzzles"]:4} {display_puzzle_count(stem):4}  '
              f'{", ".join(g.get("categories", []))}')

    playable = sum(g['numPuzzles'] for g in grids)
    display = sum(display_puzzle_count(g['file']) for g in grids)
    print(f'\n{len(grids)} grid(s), {playable} playable puzzles, '
          f'{display} display puzzles')

    # Two things that are easy to forget after adding a grid, and quiet when
    # they go wrong: an unplayable grid, and a title-screen solid with no loop
    # to show.
    unplayable = [g['file'] for g in grids if g['numPuzzles'] == 0]
    if unplayable:
        print(f'No puzzles (so absent from the picker): {", ".join(unplayable)}')
    loopless = [g['file'] for g in grids
                if g['faces'] >= TITLE_SCREEN_MIN_FACES
                and g['numPuzzles'] > 0 and display_puzzle_count(g['file']) == 0]
    if loopless:
        print(f'Big enough for the title screen but with no display puzzle: '
              f'{", ".join(loopless)}')


if __name__ == '__main__':
    main()
