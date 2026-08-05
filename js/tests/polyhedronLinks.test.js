/**
 * Tests for the About card's outbound links.
 *
 * The point of most of these is coverage against the real catalogue: the link
 * table is hand-maintained (the URLs can't be derived from names -- see the
 * chirality note in polyhedronLinks.js), so a polyhedron added to data/ would
 * otherwise silently lose its link. This turns that into a failing test.
 */
import { test, describe } from 'node:test';
import assert from 'node:assert';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

import {
    categoryLink, EULER_FORMULA_LINK, solidLink, UNLINKED_CATEGORIES,
} from '../polyhedronLinks.js';

const here = dirname(fileURLToPath(import.meta.url));
const catalogue = JSON.parse(
    readFileSync(join(here, '..', '..', 'data', 'grids.json'), 'utf8'));

describe('solidLink', () => {
    test('every grid in the catalogue has one', () => {
        const missing = catalogue.grids
            .filter(grid => solidLink(grid.gridId) === null)
            .map(grid => `${grid.gridId} (${grid.gridName})`);
        assert.deepStrictEqual(missing, [],
            'these grids have no page in polyhedronLinks.js -- add them, or the '
            + 'About card will name them without a link');
    });

    test('points at a Visual Polyhedra page', () => {
        assert.strictEqual(solidLink('aC'),
                           'https://dmccooey.com/polyhedra/Cuboctahedron.html');
    });

    test('null for a grid we know nothing about', () => {
        assert.strictEqual(solidLink('nonesuch'), null);
    });

    test('the chiral solids point at the laevo page, which is the one that exists', () => {
        // dmccooey has separate laevo/dextro pages for these and no plain one
        // (SnubCube.html is a 404), so the name can't just be PascalCased.
        assert.match(solidLink('sC'), /LsnubCube\.html$/);
        assert.match(solidLink('sD'), /LsnubDodecahedron\.html$/);
    });
});

describe('categoryLink', () => {
    test('every category in the catalogue is either linked or knowingly not', () => {
        const categories = new Set(
            catalogue.grids.flatMap(grid => grid.categories || []));
        const unaccounted = [...categories].filter(
            category => categoryLink(category) === null
                        && !UNLINKED_CATEGORIES.includes(category));
        assert.deepStrictEqual(unaccounted, [],
            'these categories are neither linked nor listed as deliberately '
            + 'unlinked in polyhedronLinks.js');
    });

    test('the families all have a background page', () => {
        for (const family of ['Platonic solid', 'Archimedean solid',
                              'Johnson solid']) {
            assert.match(categoryLink(family), /georgehart\.com/);
        }
    });

    test('null for the categories we chose not to link', () => {
        for (const category of UNLINKED_CATEGORIES) {
            assert.strictEqual(categoryLink(category), null);
        }
    });
});

describe('link hygiene', () => {
    test('every link is https', () => {
        const links = [
            EULER_FORMULA_LINK,
            ...catalogue.grids.map(grid => solidLink(grid.gridId)),
            ...catalogue.grids.flatMap(grid => (grid.categories || [])
                .map(categoryLink)),
        ].filter(Boolean);
        for (const link of links) {
            assert.match(link, /^https:\/\//, `${link} is not https`);
        }
    });

    test('no Wikipedia', () => {
        // A deliberate editorial choice, not an accident: these sources were
        // picked to teach. Keeping it as an assertion so it stays true.
        const links = [
            EULER_FORMULA_LINK,
            ...catalogue.grids.map(grid => solidLink(grid.gridId)),
            ...catalogue.grids.flatMap(grid => (grid.categories || [])
                .map(categoryLink)),
        ].filter(Boolean);
        for (const link of links) {
            assert.doesNotMatch(link, /wikipedia\.org/, `${link} is Wikipedia`);
        }
    });
});
