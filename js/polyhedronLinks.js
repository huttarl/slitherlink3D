/**
 * Where the About card sends a player who wants to know more.
 *
 * Three sources, chosen for what each does best, and deliberately not Wikipedia:
 *
 *  - Polytope Wiki (polytope.miraheze.org) for the individual solid: an article
 *    per polyhedron, with prose, pictures, a "Related polyhedra" section and
 *    hundreds of cross-links to wander through. Visual Polyhedra (dmccooey.com)
 *    was here first and is more precise, but it's a table of vital statistics --
 *    accurate and dry, which is the wrong note to end a puzzle on.
 *  - George Hart's Virtual Polyhedra (georgehart.com) for the families. These
 *    are tutorial pages with real prose and exercises, which is what someone
 *    meeting the word "Archimedean" for the first time actually needs; his
 *    per-solid links are raw .wrl model files, so they're no use here.
 *  - Plus Magazine (Cambridge's Millennium Mathematics Project) for Euler's
 *    formula: authoritative and written for a general reader.
 *
 * Every URL these produce for the current 26 grids was checked (all HTTP 200)
 * on 2026-08-04. Per-solid articles follow a rule, with a table for any
 * exceptions; the categories are a table, there being no rule to have.
 *
 * A category with no entry is fine and means "no link": the card leaves the word
 * plain rather than sending anyone somewhere unhelpful.
 *
 * ADDING A POLYHEDRON: its link is derived from its name, so it appears by
 * itself -- but nothing has checked that the page exists. Confirm with
 *
 *     npm run test:links
 *
 * which fetches every link the catalogue produces. It's skipped by the everyday
 * suite, which shouldn't need the network. If a link 404s, add an entry to
 * SOLID_PAGE_EXCEPTIONS.
 */

const POLYTOPE_WIKI = 'https://polytope.miraheze.org/wiki/';
const VIRTUAL_POLYHEDRA = 'https://www.georgehart.com/virtual-polyhedra/';

/**
 * gridId -> article title, for any solid the rule below gets wrong.
 *
 * Empty, as it happens: all 26 titles come out right, including the chiral
 * solids, which the wiki treats as one article each ('Snub cube') rather than
 * splitting them by handedness the way Visual Polyhedra does.
 *
 * Kept because the rule is a convention, not a guarantee. If a solid's article
 * sits under a different title, put it here; if the wiki hasn't got one at all,
 * qfbox.info/4d/<name> is the fallback, though its naming is irregular
 * (.../cuboctahedron exists, .../truncated_icosahedron doesn't) so each such
 * entry needs checking by hand.
 *
 * Keyed by gridId, which is not always the data file's stem: the cube's file is
 * cube.json but its gridId is 'C'.
 */
const SOLID_PAGE_EXCEPTIONS = {};

/**
 * The Polytope Wiki article title for a solid, derived from its name.
 *
 * MediaWiki titles are the plain English name with underscores for spaces, and
 * only the first word capitalized -- which is the form our gridNames are already
 * in, so this is barely a transformation. Our Johnson names carry a bracketed
 * catalogue number ("Square pyramid (J1)") which isn't part of the title.
 *
 * Holds for all 26 grids, so a grid added later gets a link for free -- but an
 * unverified one, so check it (see the note at the top of this file).
 *
 * @param {string} gridName - e.g. 'Gyroelongated square pyramid (J10)'
 * @returns {string} e.g. 'Gyroelongated_square_pyramid'
 */
function deriveArticleTitle(gridName) {
    const title = gridName
        // Drop a trailing Johnson number, and anything else parenthesized.
        .replace(/\s*\([^)]*\)\s*$/, '')
        .trim()
        .replace(/\s+/g, '_');
    // Percent-encode anything that would otherwise be structural in a URL. It
    // leaves letters, digits, underscores and hyphens alone, so ordinary titles
    // stay readable.
    return encodeURIComponent(title);
}

/**
 * Category -> the page explaining it. Full URLs, so each category can go to
 * whichever site covers it best; add a line here to link a new one.
 *
 * The families are Hart's, whose background pages teach rather than define.
 * 'chiral' is Polytope Wiki's instead, because Hart's glossary has an entry for
 * it but no per-term anchor to link to, so the link would land at the top of a
 * long glossary.
 *
 * Not every category has a page worth linking: some may be left out on
 * purpose, lacking a good source to link to.
 * Better a plain word than a disappointing link.
 */
const CATEGORY_PAGES = {
    'Platonic solid': VIRTUAL_POLYHEDRA + 'platonic-info.html',
    'Archimedean solid': VIRTUAL_POLYHEDRA + 'archimedean-info.html',
    'Johnson solid': VIRTUAL_POLYHEDRA + 'johnson-info.html',
    'deltahedron': VIRTUAL_POLYHEDRA + 'deltahedra-info.html',
    'quasiregular': VIRTUAL_POLYHEDRA + 'quasi-regular-info.html',
    'zonohedron': VIRTUAL_POLYHEDRA + 'zonohedra-info.html',
    'chiral': POLYTOPE_WIKI + 'Chirality',
    'parallelohedron': POLYTOPE_WIKI + 'Parallelohedron',
    'self-dual': POLYTOPE_WIKI + 'Self-dual_polytope',
};

/** Categories we have deliberately decided not to link (see above). */
export const UNLINKED_CATEGORIES = [];

/**
 * The article about one particular polyhedron.
 * @param {string} gridId - e.g. 'aC', used to look up the exceptions
 * @param {string} gridName - e.g. 'Cuboctahedron', which the rest derive from
 * @returns {string|null} a URL, or null without a name to work from
 */
export function solidLink(gridId, gridName) {
    const title = SOLID_PAGE_EXCEPTIONS[gridId]
        || (gridName ? deriveArticleTitle(gridName) : null);
    return title ? POLYTOPE_WIKI + title : null;
}

/** The exception table, so a test can check it's honoured. */
export const SOLID_PAGE_EXCEPTION_IDS = Object.keys(SOLID_PAGE_EXCEPTIONS);

/**
 * The page about a family or property of polyhedra.
 * @param {string} category - e.g. 'Archimedean solid', as in the catalogue
 * @returns {string|null} a URL, or null if we have none for this category
 */
export function categoryLink(category) {
    return CATEGORY_PAGES[category] || null;
}

/** Euler's formula, explained for a general reader. */
export const EULER_FORMULA_LINK = 'https://plus.maths.org/eulers-polyhedron-formula';
