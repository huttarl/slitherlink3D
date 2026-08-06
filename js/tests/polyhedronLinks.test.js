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
 * It fetches only the links it has no record of having checked, so adding one
 * solid costs one request rather than re-asking somebody else's servers for every
 * page we have ever linked to. See links-checked.json.
 */
import { test, describe } from 'node:test';
import assert from 'node:assert';
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

import {
    categoryLink, EULER_FORMULA_LINK, solidLink, SOLID_PAGE_EXCEPTION_IDS,
    UNLINKED_CATEGORIES, UNLINKED_SOLID_IDS,
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
    test('derives the article title from the polyhedron name', () => {
        assert.strictEqual(solidLink('aC', 'Cuboctahedron'),
                           'https://polytope.miraheze.org/wiki/Cuboctahedron');
        assert.strictEqual(solidLink('tI', 'Truncated icosahedron'),
                           'https://polytope.miraheze.org/wiki/Truncated_icosahedron');
    });

    test('drops a Johnson number', () => {
        assert.strictEqual(solidLink('J37', 'Elongated square gyrobicupola (J37)'),
            'https://polytope.miraheze.org/wiki/Elongated_square_gyrobicupola');
    });

    test('the chiral solids need no exception on this wiki', () => {
        // Polytope Wiki has one article each, unlike Visual Polyhedra, which
        // splits them into laevo and dextro with no plain page.
        assert.strictEqual(solidLink('sC', 'Snub cube'),
                           'https://polytope.miraheze.org/wiki/Snub_cube');
        assert.strictEqual(solidLink('sD', 'Snub dodecahedron'),
                           'https://polytope.miraheze.org/wiki/Snub_dodecahedron');
    });

    test('any exception overrides the derived title', () => {
        // Whether the entry names a different article or is null for "no article
        // at all", it has to change the answer, or it isn't doing anything.
        for (const gridId of SOLID_PAGE_EXCEPTION_IDS) {
            const entry = catalogue.grids.find(grid => grid.gridId === gridId);
            assert.ok(entry, `exception for unknown gridId ${gridId}`);
            assert.notStrictEqual(solidLink(gridId, entry.gridName),
                                  solidLink('no-exception', entry.gridName),
                                  `the exception for ${gridId} has no effect`);
        }
    });

    test('a name with punctuation still gives a usable URL', () => {
        // No current grid needs this; it's here so a name like
        // "Para-biaugmented ..." can't produce a broken URL. Hyphens are legal
        // in MediaWiki titles and are kept; only the spaces become underscores.
        assert.strictEqual(solidLink('x', 'Para-biaugmented truncated cube'),
            'https://polytope.miraheze.org/wiki/Para-biaugmented_truncated_cube');
    });

    test('null without a name to derive from', () => {
        assert.strictEqual(solidLink('nonesuch'), null);
    });

    test('every grid in the catalogue yields a well-formed URL', () => {
        // The guard on the derivation rule: a title of word characters and
        // hyphens, so a name the rule mishandles (a stray bracket, an unencoded
        // space) shows up here rather than as a 404 for a player.
        const bad = catalogue.grids
            .map(grid => [grid.gridName, solidLink(grid.gridId, grid.gridName)])
            .filter(([, url]) => url !== null)   // covered by the next test
            .filter(([, url]) =>
                !/^https:\/\/polytope\.miraheze\.org\/wiki\/[\w-]+$/.test(url));
        assert.deepStrictEqual(bad, []);
    });

    test('only the solids we chose to leave unlinked have no URL', () => {
        // A missing link should always be a decision (a null in
        // SOLID_PAGE_EXCEPTIONS), never a name the rule silently gave up on.
        const linkless = catalogue.grids
            .filter(grid => solidLink(grid.gridId, grid.gridName) === null)
            .map(grid => grid.gridId);
        assert.deepStrictEqual(linkless.sort(), [...UNLINKED_SOLID_IDS].sort());
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

    test('a category can point at a different site from the families', () => {
        // 'chiral' goes to Polytope Wiki, Hart's glossary having no per-term
        // anchor -- so the table holds full URLs rather than one site's paths.
        assert.strictEqual(categoryLink('chiral'),
                           'https://polytope.miraheze.org/wiki/Chirality');
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

    /**
     * Fetch one link, reporting its status or the failure as a string.
     *
     * One retry after a pause, because a refusal is not always an answer about
     * the URL: with the catalogue up past fifty links, firing them all at once
     * got "fetch failed" from Polytope Wiki for perfectly good pages, while the
     * same URLs answered 200 when asked more slowly.
     */
    async function statusOf(url, attempts = 2) {
        for (let attempt = 1; ; attempt++) {
            try {
                const response = await fetch(url,
                    {signal: AbortSignal.timeout(30_000)});
                if (response.status === 200 || attempt === attempts) {
                    return [url, response.status];
                }
            } catch (err) {
                if (attempt === attempts) return [url, String(err)];
            }
            await new Promise(resume => setTimeout(resume, 2000));
        }
    }

    /**
     * The links we have already fetched and found, as {url: date checked}.
     *
     * The point of keeping it: a link is worth checking when it first appears,
     * because that's when a derived URL might be wrong. Re-asking for all of
     * them on every run only loads somebody else's servers to tell us what we
     * already know. Committed alongside the code, so the record travels with the
     * links it describes.
     */
    const RECORD_PATH = join(here, 'links-checked.json');

    function readRecord() {
        try {
            return JSON.parse(readFileSync(RECORD_PATH, 'utf8'));
        } catch {
            return {};           // No record yet: everything is new.
        }
    }

    test('every link the catalogue produces returns 200',
        {skip: enabled ? false : 'set SLI_CHECK_LINKS=1 to fetch every link'},
        async () => {
            const links = [...new Set(allLinks())];
            const record = readRecord();
            // Only what we haven't checked before -- unless asked for the lot,
            // which is for the occasional audit, not for routine runs.
            const all = !!process.env.SLI_CHECK_ALL_LINKS;
            const unchecked = all ? links : links.filter(url => !record[url]);
            console.log(`${links.length} links, ${unchecked.length} to fetch `
                + `(SLI_CHECK_ALL_LINKS=1 re-checks every one)`);
            if (unchecked.length === 0) return;

            // A few at a time, not all at once: these are somebody's servers,
            // and hammering them turns a link check into a load test.
            const results = [];
            const AT_A_TIME = 4;
            for (let i = 0; i < unchecked.length; i += AT_A_TIME) {
                results.push(...await Promise.all(
                    unchecked.slice(i, i + AT_A_TIME).map(url => statusOf(url))));
            }
            const broken = results.filter(([, status]) => status !== 200);

            // Record the ones that answered, so the next run leaves them alone.
            // Written even when others failed: what was verified stays verified,
            // and re-fetching it would not help diagnose the failure.
            const today = new Date().toISOString().slice(0, 10);
            for (const [url, status] of results) {
                if (status === 200) record[url] = today;
            }
            writeFileSync(RECORD_PATH,
                JSON.stringify(sortedByKey(record), null, 2) + '\n');

            assert.deepStrictEqual(broken, [],
                `${unchecked.length} links fetched; these did not return 200`);
        });
});

/** An object with its keys in order, so the record file's diffs stay readable. */
function sortedByKey(object) {
    return Object.fromEntries(Object.keys(object).sort()
        .map(key => [key, object[key]]));
}
