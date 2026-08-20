"""Tests for build_catalogue.py's handling of the lore registry.

data/lore.json is hand-edited, so the validation is the whole safety
story: a typo there must stop the catalogue build loudly, never become lore
that quietly fails to reach the app. These tests pin the validator's rules,
the folding of lore onto catalogue entries, and — as an integration check —
that the registry actually in data/ passes against the grids actually there.
"""
import json

import pytest

from build_catalogue import (DATA_DIR, fold_lore, load_lore, validate_lore)

KNOWN = {'C', 'O', 'tI', 'dtI'}


def entry(grid_id):
    """A minimal catalogue entry, as build_entry would make it."""
    return {'gridId': grid_id, 'gridName': grid_id, 'numPuzzles': 3}


class TestValidateLore:
    def test_a_valid_registry_passes(self):
        validate_lore({'tI': {'aliases': ['buckyball']}},
                      [['C', 'O'], ['tI', 'dtI']], KNOWN)

    def test_empty_registry_passes(self):
        validate_lore({}, [], KNOWN)

    def test_unknown_grid_id_in_solids(self):
        with pytest.raises(ValueError, match="solids\\['tX'\\]"):
            validate_lore({'tX': {'aliases': ['ghost']}}, [], KNOWN)

    def test_unknown_attribute_is_a_typo(self):
        with pytest.raises(ValueError, match="unknown attribute 'aliasses'"):
            validate_lore({'tI': {'aliasses': ['buckyball']}}, [], KNOWN)

    def test_aliases_must_be_a_list_of_strings(self):
        with pytest.raises(ValueError, match='non-empty list'):
            validate_lore({'tI': {'aliases': 'buckyball'}}, [], KNOWN)
        with pytest.raises(ValueError, match='non-empty list'):
            validate_lore({'tI': {'aliases': []}}, [], KNOWN)
        with pytest.raises(ValueError, match='non-empty list'):
            validate_lore({'tI': {'aliases': ['buckyball', '']}}, [], KNOWN)

    def test_solid_attributes_must_be_a_dictionary(self):
        with pytest.raises(ValueError, match='expected a dictionary'):
            validate_lore({'tI': ['buckyball']}, [], KNOWN)

    def test_unknown_grid_id_in_duals(self):
        with pytest.raises(ValueError, match="no grid in data/ has gridId 'tX'"):
            validate_lore({}, [['tX', 'C']], KNOWN)

    def test_a_solid_in_two_pairs(self):
        with pytest.raises(ValueError, match="'C' appears in more than one pair"):
            validate_lore({}, [['C', 'O'], ['C', 'tI']], KNOWN)

    def test_self_pair_is_refused(self):
        # Self-duals are the 'self-dual' category's job, not the pair list's.
        with pytest.raises(ValueError, match='self-dual'):
            validate_lore({}, [['C', 'C']], KNOWN)

    def test_malformed_pair(self):
        with pytest.raises(ValueError, match='not a pair'):
            validate_lore({}, [['C']], KNOWN)
        with pytest.raises(ValueError, match='not a pair'):
            validate_lore({}, ['CO'], KNOWN)

    def test_all_problems_reported_at_once(self):
        # Hand-editors should see the whole list, not fix-rerun-fix.
        with pytest.raises(ValueError) as excinfo:
            validate_lore({'tX': {'aliases': ['ghost']}},
                          [['C', 'C'], ['O', 'yY']], KNOWN)
        message = str(excinfo.value)
        assert "solids['tX']" in message
        assert 'self-dual' in message
        assert "'yY'" in message


class TestFoldLore:
    def test_aliases_and_both_dual_directions_land(self):
        entries = [entry('C'), entry('O'), entry('tI')]
        fold_lore(entries,
                  {'tI': {'aliases': ['buckyball', 'soccer ball']}},
                  [['C', 'O']])
        by_id = {e['gridId']: e for e in entries}
        assert by_id['tI']['aliases'] == ['buckyball', 'soccer ball']
        # The pair is stored once but read from either side.
        assert by_id['C']['dual'] == 'O'
        assert by_id['O']['dual'] == 'C'

    def test_solids_without_lore_gain_no_keys(self):
        # Absent rather than empty, like every optional key in the data files.
        entries = [entry('C'), entry('O')]
        fold_lore(entries, {'C': {'aliases': ['regular hexahedron']}}, [])
        assert 'aliases' not in entries[1]
        assert all('dual' not in e for e in entries)


class TestTheRealRegistry:
    """The registry actually in data/ stays valid against the actual grids."""

    def test_data_registry_validates(self):
        (solids, duals) = load_lore()
        known_ids = set()
        for path in DATA_DIR.glob('*.json'):
            if path.stem.endswith('-puzzles') or path.name in (
                    'grids.json', 'lore.json'):
                continue
            known_ids.add(json.loads(path.read_text())['gridId'])
        validate_lore(solids, duals, known_ids)

    def test_missing_registry_is_fine(self, tmp_path):
        assert load_lore(tmp_path / 'lore.json') == ({}, [])
