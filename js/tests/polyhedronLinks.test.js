/**
 * Tests for the About card's outbound links.
 *
 * The per-solid URLs are derived from the polyhedron's name, so most of these
 * check the rule and its exceptions. One test runs over the real catalogue and
 * insists every name yields a well-formed URL -- that's what catches a name the
 * rule mangles (a stray bracket or space reaching the URL) without pinning all
 * 26 by hand.
 *
 * Whether the pages actually EXIST is the last test, and it needs the network,
 * so it only runs with SLI_CHECK_LINKS=1. Run that after adding a polyhedron.
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

/** Every link the card can produce for the catalogue as it stands. */
function allLinks() {
    return [
        EULER_FORMULA_LINK,
        ...catalogue.grids.map(grid => solidLink(grid.gridId, grid.gridName)),
        ...catalogue.grids.flatMap(
            grid => (grid.categories || []).map(categoryLink)),
    ].filter(Boolean);
}

describe('solidLink', () => {
    test('derives the page name from the polyhedron name', () => {
        assert.strictEqual(solidLink('aC', 'Cuboctahedron'),
                           'https://dmccooey.com/polyhedra/Cuboctahedron.html');
        assert.strictEqual(solidLink('tI', 'Truncated icosahedron'),
                           'https://dmccooey.com/polyhedra/TruncatedIcosahedron.html');
    });

    test('drops a Johnson number', () => {
        assert.strictEqual(solidLink('J37', 'Elongated square gyrobicupola (J37)'),
            'https://dmccooey.com/polyhedra/ElongatedSquareGyrobicupola.html');
    });

    test('the chiral solids are exceptions, pointing at the page that exists', () => {
        // Visual Polyhedra splits these into laevo and dextro and has no plain
        // page -- SnubCube.html is a 404 -- so the rule alone would break them.
        assert.match(solidLink('sC', 'Snub cube'), /LsnubCube\.html$/);
        assert.match(solidLink('sD', 'Snub dodecahedron'), /LsnubDodecahedron\.html$/);
    });

    test('an exception wins over the derived name', () => {
        assert.doesNotMatch(solidLink('sC', 'Snub cube'), /SnubCube\.html$/);
    });

    test('a hyphenated or punctuated name still gives a clean filename', () => {
        // No current grid needs this; it's here so a name like "Para-biaugmented
        // ..." can't put a hyphen or an apostrophe in a URL.
        assert.strictEqual(solidLink('x', 'Para-biaugmented truncated cube'),
            'https://dmccooey.com/polyhedra/ParaBiaugmentedTruncatedCube.html');
    });

    test('null without a name to derive from', () => {
        assert.strictEqual(solidLink('nonesuch'), null);
    });

    test('every grid in the catalogue yields a well-formed URL', () => {
        // The guard on the derivation rule: letters and digits only, so a name
        // the rule mishandles shows up here rather than as a 404 for a player.
        const bad = catalogue.grids
            .map(grid => [grid.gridName, solidLink(grid.gridId, grid.gridName)])
            .filter(([, url]) =>
                !/^https:\/\/dmccooey\.com\/polyhedra\/[A-Za-z0-9]+\.html$/.test(url));
        assert.deepStrictEqual(bad, []);
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
        for (const link of allLinks()) {
            assert.match(link, /^https:\/\//, `${link} is not https`);
        }
    });

    test('no Wikipedia', () => {
        // A deliberate editorial choice, not an accident: these sources were
        // picked to teach. Keeping it as an assertion so it stays true.
        for (const link of allLinks()) {
            assert.doesNotMatch(link, /wikipedia\.org/, `${link} is Wikipedia`);
        }
    });
});

describe('the pages exist', () => {
    // Network, so opt-in: the everyday suite must run offline and fast. This is
    // the check that a derived URL is real, which is the one thing deriving
    // rather than tabulating gives up.
    const enabled = !!process.env.SLI_CHECK_LINKS;

    test('every link the catalogue produces returns 200',
        {skip: enabled ? false : 'set SLI_CHECK_LINKS=1 to fetch every link'},
        async () => {
            const links = [...new Set(allLinks())];
            const results = await Promise.all(links.map(async url => {
                try {
                    const response = await fetch(url,
                        {signal: AbortSignal.timeout(30_000)});
                    return [url, response.status];
                } catch (err) {
                    return [url, String(err)];
                }
            }));
            const broken = results.filter(([, status]) => status !== 200);
            assert.deepStrictEqual(broken, [],
                `${links.length} links checked; these did not return 200`);
        });
});
