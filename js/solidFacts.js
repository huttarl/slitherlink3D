/**
 * Facts about a polyhedron worked out from its own topology.
 *
 * Nothing here needs a catalogue entry, a data file, or hand-written prose: the
 * grid knows how many faces of each kind it has and how they meet, which turns
 * out to be most of what makes one solid feel different from another. The point
 * is to show a player what "Archimedean" or "deltahedron" MEANS about the shape
 * in front of them, rather than asserting a definition.
 *
 * Pure functions over a Grid -- no DOM, no THREE -- so they unit-test headless
 * (see js/tests/solidFacts.test.js).
 */

/**
 * Names for the polygons that turn up in these solids, by side count alone.
 *
 * "quadrilateral" rather than "square", because a four-sided face is only a
 * square on the solids whose faces are regular: the rhombic dodecahedron's
 * twelve faces are rhombi, and a deltoidal icositetrahedron's are kites. Where
 * the corners are known, faceName measures instead of guessing.
 */
const POLYGON_NAMES = {
    3: 'triangle', 4: 'quadrilateral', 5: 'pentagon', 6: 'hexagon',
    7: 'heptagon', 8: 'octagon', 9: 'nonagon', 10: 'decagon', 12: 'dodecagon',
};

/** Plurals that aren't just -s. */
const IRREGULAR_PLURALS = {rhombus: 'rhombi'};

/** How much two lengths may differ and still count as equal, as a fraction of
 *  the larger. Generous, because grid coordinates are stored rounded (three
 *  decimals for anything that came through obj2json.py) -- and because a shape
 *  that misses being a square by more than 2% is one a player would see isn't
 *  one. */
const SHAPE_TOLERANCE = 0.02;

function pluralOf(name) {
    return IRREGULAR_PLURALS[name] || name + 's';
}

/**
 * What to call a polygon with this many sides, knowing nothing else about it.
 * @param {number} sides
 * @param {boolean} [plural]
 * @returns {string} e.g. "hexagon", "hexagons", "14-gons"
 */
export function polygonName(sides, plural = false) {
    const name = POLYGON_NAMES[sides] || `${sides}-gon`;
    return plural ? pluralOf(name) : name;
}

function distanceBetween(p, q) {
    return Math.hypot(p.x - q.x, p.y - q.y, p.z - q.z);
}

/** Are these lengths all the same, within SHAPE_TOLERANCE? */
function allEqual(lengths) {
    const largest = Math.max(...lengths);
    return largest - Math.min(...lengths) <= SHAPE_TOLERANCE * largest;
}

/**
 * What to call a quadrilateral with these corners, in order round it.
 *
 * Equal sides and equal diagonals make a square; equal sides alone a rhombus
 * (which is what the rhombic dodecahedron and triacontahedron are made of, and
 * worth saying, since it's where they get their names). Anything else is left as
 * a quadrilateral -- a kite could be named too, but "kite" isn't the word a
 * player would check against the solid's own name.
 *
 * @param {Array<{x: number, y: number, z: number}>} corners - four, in order
 * @returns {string} 'square', 'rhombus' or 'quadrilateral'
 */
export function quadrilateralName(corners) {
    const sides = corners.map((corner, i) =>
        distanceBetween(corner, corners[(i + 1) % corners.length]));
    if (!allEqual(sides)) return 'quadrilateral';
    return allEqual([distanceBetween(corners[0], corners[2]),
                     distanceBetween(corners[1], corners[3])])
        ? 'square' : 'rhombus';
}

/** The corners of a face as points, or null if the grid hasn't real coordinates
 *  (which is the case for the topology-only grids the unit tests build). */
function cornersOf(grid, face) {
    const corners = face.vertexIDs.map(id => grid.vertices.get(id)?.position);
    const usable = corners.every(p => p && Number.isFinite(p.x)
        && Number.isFinite(p.y) && Number.isFinite(p.z));
    return usable ? corners : null;
}

/**
 * What to call one face of a grid: its side count's name, refined by measuring
 * where that says more (see quadrilateralName).
 */
function faceName(grid, face) {
    if (face.vertexIDs.length !== 4) return polygonName(face.vertexIDs.length);
    const corners = cornersOf(grid, face);
    return corners ? quadrilateralName(corners) : polygonName(4);
}

/**
 * How many faces of each kind the solid has.
 *
 * Kinds, not side counts: squares and rhombi are counted apart, so a solid with
 * both would report both. Ordered by side count, and by name within it.
 *
 * @param {Grid} grid
 * @returns {Array<{sides: number, name: string, count: number}>}
 */
export function faceCensus(grid) {
    const counts = new Map();
    for (const face of grid.faces.values()) {
        const kind = `${face.vertexIDs.length} ${faceName(grid, face)}`;
        const seen = counts.get(kind);
        counts.set(kind, {sides: face.vertexIDs.length,
                          name: faceName(grid, face),
                          count: (seen ? seen.count : 0) + 1});
    }
    return [...counts.values()]
        .sort((a, b) => a.sides - b.sides || a.name.localeCompare(b.name));
}

/**
 * The census in words: "8 triangles, 6 squares".
 * @param {Array<{sides: number, name: string, count: number}>} census - from
 *     faceCensus
 * @returns {string}
 */
export function describeFaceCensus(census) {
    if (census.length === 1) {
        // Only one type of face (Platonic solid)
        return `all ${pluralOf(census[0].name)}`
    } else {
        return census
            .map(({name, count}) =>
                `${count} ${count !== 1 ? pluralOf(name) : name}`)
            .join(', ');
    }
}

/**
 * The faces meeting at one vertex, in the cyclic order they go round it.
 *
 * Walks the fan: from an edge at the vertex, into a face, across that face to
 * its other edge at the same vertex, through that edge to the next face, and on
 * until the starting edge comes back round. The cyclic ORDER is the point --
 * a vertex where a triangle and a square alternate (3.4.3.4, the cuboctahedron)
 * is a different shape from one where the two triangles are adjacent (3.3.4.4),
 * so counting face kinds at the vertex would miss the distinction.
 *
 * @param {Grid} grid
 * @param {number} vertexId
 * @returns {number[]|null} side counts in cyclic order, starting somewhere
 *     arbitrary and running in an arbitrary direction (canonicalize before
 *     comparing -- see vertexConfiguration); null if the faces at this vertex
 *     don't form a closed fan, which a well-formed closed polyhedron rules out
 */
export function facesAroundVertex(grid, vertexId) {
    const vertex = grid.vertices.get(vertexId);
    if (!vertex || vertex.edgeIDs.size === 0) return null;
    const edgesHere = vertex.edgeIDs;

    const startEdgeId = [...edgesHere][0];
    let edgeId = startEdgeId;
    // Either face of the starting edge will do: the fan can be walked in either
    // direction, and the result is canonicalized before it's compared.
    let faceId = [...grid.edges.get(edgeId).faceIDs][0];
    if (faceId === undefined) return null;

    const sides = [];
    // The fan visits one face per edge at the vertex, so that count also caps
    // the walk: a malformed grid can't spin here forever.
    for (let step = 0; step < edgesHere.size; step++) {
        sides.push(grid.faces.get(faceId).vertexIDs.length);

        const face = grid.faces.get(faceId);
        // This face's other edge at the vertex...
        const nextEdgeId = face.edgeIDs.find(
            id => id !== edgeId && edgesHere.has(id));
        if (nextEdgeId === undefined) return null;
        // ...and the face on the far side of it.
        const nextFaceId = [...grid.edges.get(nextEdgeId).faceIDs]
            .find(id => id !== faceId);
        if (nextFaceId === undefined) return null;

        edgeId = nextEdgeId;
        faceId = nextFaceId;
        if (edgeId === startEdgeId) return sides;   // all the way round
    }
    return null;   // Never closed up.
}

/** Compares two equal-length sequences of numbers, first difference wins. */
function compareSequences(a, b) {
    for (let i = 0; i < a.length; i++) {
        if (a[i] !== b[i]) return a[i] - b[i];
    }
    return 0;
}

/**
 * The one form of a cyclic sequence that two equivalent vertices always share.
 *
 * A fan can be walked from any of its edges and in either direction, so the raw
 * sequence differs between vertices that are in fact alike. Taking the smallest
 * rotation of the sequence and of its reverse removes both freedoms. Numeric
 * comparison, not string: a truncated dodecahedron's 3.10.10 would sort wrong
 * as text ("10" < "3").
 *
 * @param {number[]} sides
 * @returns {number[]}
 */
function canonicalCycle(sides) {
    let best = null;
    for (const direction of [sides, [...sides].reverse()]) {
        for (let i = 0; i < direction.length; i++) {
            const rotation = [...direction.slice(i), ...direction.slice(0, i)];
            if (best === null || compareSequences(rotation, best) < 0) {
                best = rotation;
            }
        }
    }
    return best;
}

/**
 * The solid's vertex configuration, if every vertex has the same one.
 *
 * Sameness at every vertex is what the Platonic and Archimedean definitions
 * turn on, so this doubles as a test of it: a Johnson solid has vertices of
 * several kinds and gets null, which is the honest answer and also the reason
 * the card says nothing about them.
 *
 * @param {Grid} grid
 * @returns {number[]|null} the shared cycle of face sizes (e.g. [3, 4, 3, 4]),
 *     or null if the vertices differ (or the topology is malformed)
 */
export function vertexConfiguration(grid) {
    let shared = null;
    for (const vertexId of grid.vertices.keys()) {
        const cycle = facesAroundVertex(grid, vertexId);
        if (cycle === null) return null;
        const canonical = canonicalCycle(cycle);
        if (shared === null) {
            shared = canonical;
        } else if (shared.length !== canonical.length
                   || compareSequences(shared, canonical) !== 0) {
            return null;   // Vertices are not all alike.
        }
    }
    return shared;
}

/**
 * A vertex configuration in the usual notation: [3, 4, 3, 4] -> "3.4.3.4".
 * @param {number[]} cycle
 * @returns {string}
 */
export function vertexConfigurationNotation(cycle) {
    return cycle.join('.');
}

/**
 * A naming function for this solid's faces, from its census.
 *
 * A vertex configuration is a cycle of side COUNTS, so on its own it can't tell a
 * square from a rhombus. This bridges the gap: where every face of a given size
 * on this solid is the same kind, that kind's name is used, and where they differ
 * the plain name for the side count is. A cube's 4 is therefore a square, a
 * rhombic dodecahedron's a rhombus, and a hypothetical solid with both gets
 * "quadrilateral".
 *
 * @param {Array<{sides: number, name: string}>} census - from faceCensus
 * @returns {function(number): string}
 */
export function faceNamer(census) {
    const names = new Map();
    for (const {sides, name} of census) {
        names.set(sides, names.has(sides) && names.get(sides) !== name
            ? polygonName(sides) : name);
    }
    return sides => names.get(sides) || polygonName(sides);
}

/**
 * A vertex configuration in words: "triangle, square, triangle, square".
 * @param {number[]} cycle
 * @param {function(number): string} [nameFor] - what to call a face with this
 *     many sides; pass faceNamer(census) to have measured names used
 * @returns {string}
 */
export function describeVertexConfiguration(cycle, nameFor = polygonName) {
    return cycle.map(sides => nameFor(sides)).join(', ');
}
