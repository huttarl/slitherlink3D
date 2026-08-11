/**
 * Where the About card sends a player who wants to know more.
 *
 * Various sources, chosen for what each does best:
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
 *  - Wikipedia is a great go-to, but it has a huge amount of power to shape
 *    public opinion concentrated in the hands of one organization. I'd rather
 *    contribute to decentralizing authority over knowledge. So I'm using other
 *    sources.
 *
 * Every URL these produce should be checked (all HTTP 200).
 * Per-solid articles follow a rule, with a table for any
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
 * Nearly empty: all the named solids' titles come out right, including the
 * chiral ones, which the wiki treats as one article each ('Snub cube') rather
 * than splitting them by handedness the way Visual Polyhedra does.
 *
 * The exception is a solid the wiki has no article for, only a family one. If
 * that happens again, and the family article isn't a good landing place either,
 * qfbox.info/4d/<name> is the fallback, though its naming is irregular
 * (.../cuboctahedron exists, .../truncated_icosahedron doesn't) so each such
 * entry needs checking by hand.
 *
 * Keyed by gridId, which is not always the data file's stem: the cube's file is
 * cube.json but its gridId is 'C'.
 */
const SOLID_PAGE_EXCEPTIONS = {
    // The wiki covers the Goldberg polyhedra in one article and has nothing on
    // GP(1,2) by itself, so that article is where the name should lead. (The rule
    // would derive 'Goldberg_GP' from "Goldberg GP(1,2)" -- it strips a trailing
    // parenthetical, which here is part of the name.) The chamfered dodecahedron,
    // GP(2,0), needs no entry: it has a name and an article of its own.
    'gp12': 'Goldberg_polyhedron',
    // null: no article anywhere, so the card leaves the name as plain text. The
    // random solids (util/genRandomPolyh.py) are one-offs nobody has written
    // about -- and unlike a missing entry, this can't quietly become a 404.
    //
    // The two geodesics are here for a different reason: they are perfectly
    // well-known solids, but this wiki has nothing on the geodesic polyhedra at
    // all -- not even the family article that gp12 above falls back on. So the
    // reading for them is the 'geodesic' category link instead, and the name
    // stays plain. (The derivation would give 'Geodesic_GD' anyway, stripping the
    // "(2,0)" that is part of the name, exactly as for GP(1,2).)
    'gd20': null,
    'gd21': null,
    // The tetrakis snub cube is the geodesic on an octahedron rather than an
    // icosahedron; the wiki has no article on it under that name or any other.
    'dwC': null,
    'etI': null,
    // The zonish solids (util/genZonish.py). Their names are Hart's descriptions of
    // his own figures rather than established names, so there is no article to find
    // -- and unlike the geodesics, the 'zonish' category link goes to the very page
    // the solids came from, which is the best reading available anyway. J43 needs no
    // entry: it is a Johnson solid with an article of its own, which is worth
    // knowing about it.
    'zonaC4': null,
    'zonaD2': null,
    'zonaD3o': null,
    'zonaD3p': null,
    'zonaD6': null,
    'RandomsphereA': null,
    'RandomsphereC': null,
    'RandomsphereD': null,
    'RandomsphereE': null,
};

/**
 * The Polytope Wiki article title for a solid, derived from its name.
 *
 * MediaWiki titles are the plain English name with underscores for spaces, and
 * only the first word capitalized -- which is the form our gridNames are already
 * in, so this is barely a transformation. Our Johnson names carry a bracketed
 * catalogue number ("Square pyramid (J1)") which isn't part of the title.
 *
 * Holds for every solid with a name of its own, so a grid added later gets a
 * link for free -- but an unverified one, so check it (see the note at the top of
 * this file). It does NOT hold for a name ending in a parenthesis that belongs to
 * it, like "Goldberg GP(1,2)": that one is in SOLID_PAGE_EXCEPTIONS.
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
    // Hart files the Catalan solids under what they are -- the Archimedean duals
    // -- which is also the more useful page to land on, since it explains where
    // they come from rather than just listing them.
    'Catalan solid': VIRTUAL_POLYHEDRA + 'archimedean-duals-info.html',
    'Johnson solid': VIRTUAL_POLYHEDRA + 'johnson-info.html',
    'deltahedron': VIRTUAL_POLYHEDRA + 'deltahedra-info.html',
    'quasiregular': VIRTUAL_POLYHEDRA + 'quasi-regular-info.html',
    'zonohedron': VIRTUAL_POLYHEDRA + 'zonohedra-info.html',
    'chiral': POLYTOPE_WIKI + 'Chirality',
    'Goldberg': POLYTOPE_WIKI + 'Goldberg_polyhedron',
    // Both are infinite families, so the wiki has an article about the family
    // rather than a category page -- which is what a player wants here anyway:
    // the cube is a prism, and the point is what that means.
    'prism': POLYTOPE_WIKI + 'Prism',
    'antiprism': POLYTOPE_WIKI + 'Antiprism',
    'parallelohedron': POLYTOPE_WIKI + 'Parallelohedron',
    'self-dual': POLYTOPE_WIKI + 'Self-dual_polytope',
    'geodesic': 'https://geometryofthinking.com/2024/02/01/geodesics/',
    // Hart again, and the rare case where the page that explains a category is also
    // the page these solids came from: util/genZonish.py reproduces its figures.
    'zonish': VIRTUAL_POLYHEDRA + 'zonish_polyhedra.html',
    'Near-miss Johnson solid': POLYTOPE_WIKI + 'Near-miss_Johnson_solid',
};

/** Categories we have deliberately decided not to link (see above). */
export const UNLINKED_CATEGORIES = [
    // The catch-all family (see FAMILY_ORDER in catalogue.js). There is nothing
    // to read about being miscellaneous; what such a solid actually is shows in
    // its other categories, which are linked.
    'Miscellaneous',
];

/**
 * The article about one particular polyhedron.
 * @param {string} gridId - e.g. 'aC', used to look up the exceptions
 * @param {string} gridName - e.g. 'Cuboctahedron', which the rest derive from
 * @returns {string|null} a URL, or null without a name to work from
 */
export function solidLink(gridId, gridName) {
    // An entry of null says "no article anywhere", which is the honest answer
    // for a solid nobody has written about -- the random ones. Distinct from a
    // missing entry, which means "the rule below gets this right".
    if (gridId in SOLID_PAGE_EXCEPTIONS && SOLID_PAGE_EXCEPTIONS[gridId] === null) {
        return null;
    }
    const title = SOLID_PAGE_EXCEPTIONS[gridId]
        || (gridName ? deriveArticleTitle(gridName) : null);
    return title ? POLYTOPE_WIKI + title : null;
}

/** The exception table, so a test can check it's honoured. */
export const SOLID_PAGE_EXCEPTION_IDS = Object.keys(SOLID_PAGE_EXCEPTIONS);

/** The solids we have deliberately left unlinked (a null entry above). */
export const UNLINKED_SOLID_IDS = Object.keys(SOLID_PAGE_EXCEPTIONS)
    .filter(gridId => SOLID_PAGE_EXCEPTIONS[gridId] === null);

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

/**
 * "An Enduring Error": the paper on how the elongated square gyrobicupola (J37)
 * spent centuries being miscounted as an Archimedean solid, because it has the
 * rhombicuboctahedron's 3.4.4.4 at every vertex without the symmetry that would
 * carry any vertex to any other. Linked from the card's note on exactly that
 * catch (see buildAboutCard in aboutSolid.js).
 *
 * Named here rather than inlined at the point of use so the link tests cover it:
 * allLinks() in the test is what gets checked for HTTPS and, under
 * SLI_CHECK_LINKS=1, actually fetched.
 */
export const ENDURING_ERROR_LINK =
    'https://ems.press/content/serial-article-files/45375';
