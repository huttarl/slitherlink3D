/* Slitherlink 3D, Copyright 2018 by Lars Huttar

    Terminology: I'll try to use "cell" to refer to a polygonal face of a polygon,
    because in Three.js and some other graphics contexts, "face" means a triangle
    or quad into which such polygons are subdivided.

    Operations needed:
    x Come up with a sample puzzle to test with.
    - Display cell numbers!
    x Display edges
      x Don't display them twice.
      - Display a different color for each edge's state.
    - Pick an edge with mouse; see https://threejs.org/examples/?q=inter#webgl_interactive_lines
    - Display edges wider? If so, probably use https://github.com/spite/THREE.MeshLine
    - Display vertices?
    x Load/parse json mesh data
    x Separate script to convert .obj to .json format
    x Camera smooth zoom after mesh loaded.
    x Import geometry from source into THREE.js structures (LineSegments, mesh, Dots?)
    - Import geometry from source into program data structures (possibly a halfedge DS?)
    - Pick a cell - see https://threejs.org/examples/#webgl_interactive_buffergeometry
    - Pick a vertex?
    - Change an edge from one material to another; that apparently means
      having to move it from one LineSegments to another. UNLESS... we can do
      it by changing its texture coordinates. Can we do that with THREE.MeshLine?
    - Display a "loading" spinner while loading?
    - Develop code, or adapt Krazydad's, for creating puzzles for a given mesh.
*/

var MAX_POINTS = 1000, MAX_EDGES = 1000, MAX_CELLS = 1000;

// Mesh to load. Points are assumed to be centered around origin.
var dataURL = 'data/';
var DEFAULT_DATA_FILE='phe-T.json';

var renderer, scene, camera, sphere, clueFont;

var puzzles, board;
var cluesAdded, clueFont;

var maxR = 1; // max distance from origin.
var maxR2 = 0; // maxR squared
var camR = 4 * maxR; // distance of camera
var autoRotating = true;

init();
animate();

function init() {
    // TODO: make antialias a controllable option?
    renderer = new THREE.WebGLRenderer({antialias:  true});
    renderer.setPixelRatio( window.devicePixelRatio );
    renderer.setSize( window.innerWidth, window.innerHeight );
    document.body.appendChild( renderer.domElement );

    scene = new THREE.Scene();

    camera = new THREE.PerspectiveCamera(
        35,             // Field of view
        800 / 600,      // Aspect ratio
        0.5,            // Near plane
        6              // Far plane
    );
    camera.position.set( camR, 0, 0 );
    camera.lookAt( scene.position );

    controls = new THREE.TrackballControls( camera );
    controls.rotateSpeed = 2.0;
    controls.zoomSpeed = 1.2;
    controls.panSpeed = 0.8;
    controls.noZoom = false;
    controls.noPan = false;
    controls.staticMoving = false;
    controls.dynamicDampingFactor = 0.2;
    controls.keys = [ 65, 83, 68 ];
    // Don't need the following if we use an animation loop?
    controls.addEventListener( 'change', changeControls );

    var light = new THREE.PointLight( 0xFFFF00 );
    light.position.set( 10, 10, 10 );
    scene.add( light );

    var loader = new THREE.FontLoader();
    loader.load( 'fonts/helvetiker_regular.typeface.json', useFont, reportProgress, loadingError);

    renderer.setClearColor( 0, 1);
    render();

    window.addEventListener( 'resize', onWindowResize, false );

    fetch(dataURL + DEFAULT_DATA_FILE)
      .then(status)
      .then(responseToJSON)
      .then(function(data) {
        // console.log('Request succeeded with JSON response', data);
        importData(data);
      }).catch(function(error) {
        // TODO: inform the user?
        console.log('Request failed', error);
      });
}

// TODO: I don't think this is consistent with how we start...
// maybe subtract a right and/or bottom margin?
function onWindowResize() {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize( window.innerWidth, window.innerHeight );
    controls.handleResize();
    render();
}

// Load JSON:
function status(response) {
  if (response.status >= 200 && response.status < 300) {
    return Promise.resolve(response);
  } else {
    return Promise.reject(new Error(response.statusText));
  }
}

function responseToJSON(response) {
  return response.json();
}

/** Length squared, of vector. */
function length2(v) {
    return v[0]*v[0] + v[1]*v[1] + v[2]*v[2];
}

function updateMaxR(v) {
    var d2 = length2(v);
    if (d2 > maxR2) maxR2 = d2;
}

/** Pull data into Three.js and app data structures. */
function importData(data) {
	console.log("Import data");
	
	// Global data structures
	puzzles = data.puzzles;
	board = data;
	
    // // geometry
    // var geometry = new THREE.BufferGeometry();

    // // attributes
    // var positions = new Float32Array( MAX_POINTS * 3 ); // 3 vertices per point
    // geometry.addAttribute( 'position', new THREE.BufferAttribute( positions, 3 ) );
    var geometry = new THREE.Geometry();
    
    maxR2 = 0;

    var edgesAddedToMesh = {};

    for (var c=0; c < data.cells.length; c++) {
        var cell = data.cells[c];
        for (var v=0; v < cell.length; v++) {
            var nv = (v+1 >= cell.length) ? 0 : v+1;
            // Check: is the reversed edge already added? If so don't add it again.
            if ([cell[nv], cell[v]] in edgesAddedToMesh) {
                // console.log("Edge already added", cell[v], cell[nv]);
                continue;
            }
            // Add this edge.
            edgesAddedToMesh[[cell[v], cell[nv]]] = true;

            var v1 = Vector3FromArray(data.vertices[cell[v]]),
				v2 = Vector3FromArray(data.vertices[cell[nv]]);
            updateMaxR(v1);
            geometry.vertices.push(v1);
            // was: new (Function.prototype.bind.apply(THREE.Vector3, data.vertices[cell[v]-1])));
            updateMaxR(v2);
            geometry.vertices.push(v2);
            // was: new (Function.prototype.bind.apply(THREE.Vector3, data.vertices[cell[nv]-1])));
        }
    }

    maxR = Math.sqrt(maxR2);
    console.log("maxR: ", maxR);

    var material = new THREE.LineBasicMaterial( { color: 0xff888888, linewidth: 6 } ); // 0xff888888
    sphere = new THREE.LineSegments( geometry, material );

    scene.add(sphere);

    autoRotating = true; // autorotate at first?
	
	if (clueFont && !cluesAdded) addClues();
}

function Vector3FromArray(a) {
	return new THREE.Vector3(a[0], a[1], a[2]);
	// We could get fancy and do something like this:
    // new (Function.prototype.bind.apply(THREE.Vector3, [null, a, b, c]));
    // But I guess we'd have to put null on the front of the array...
}

/** Linear interpolation */
// Precise method, which guarantees v = v1 when t = 1.
// https://en.wikipedia.org/wiki/Linear_interpolation#Programming_language_support
function lerp(v0, v1, t) {
    return (1 - t) * v0 + t * v1;
}

function animate() {
    if (autoRotating && sphere !== undefined) {
		// Do this via controls if at all?
        // sphere.rotation.x += 0.0005;
        // sphere.rotation.y += 0.0005;
        // console.log("Rotated");
    }

    camR = lerp(camR, 4 * maxR, 0.15);
    // camera.position.set( camR, 0, 0 );
    // camera.lookAt( scene.position );
	// TODO: how to adjust camera distance when using Trackball?

    // console.log("animate");
    requestAnimationFrame( animate );
    controls.update();
    // not needed?
    render();
}

function render() {
    // console.log("render");
    renderer.render( scene, camera );
}

function changeControls() {
    // console.log("changeControls");
    // Stop autorotating when user touches controls.
    autoRotating = false;
    render();
}

// Function called after font is loaded.
// TODO: change this function to what we need.
function useFont( font ) {
    console.log("Font loaded...");
	clueFont = font;
	// Check whether we need to wait still for puzzles to load.
	if (puzzles && !cluesAdded) {
		addClues();
	}
}

function addClues() {
	addCellClue(0, 0);
	// TODO: add clues for all cells that need them.
	cluesAdded = true;
}

/** Add an object to the scene representing the clue for cell c in puzzle p. */
function addCellClue(p, c) {	
	clue = "" + puzzles[p][c];
	cell = board.cells[c];
	if (cell.normal === undefined) computeCell(cell);
	
    var xMid, text;
    var textShape = new THREE.BufferGeometry();
    var color = 0x006699;
    var matDark = new THREE.LineBasicMaterial( {
        color: color,
        side: THREE.DoubleSide // TODO: change to single?
    } );
    var matLite = new THREE.MeshBasicMaterial( {
        color: color,
        transparent: true,
        opacity: 0.4,
        side: THREE.DoubleSide // TODO: change to single?
    } );
    var shapes = clueFont.generateShapes( clue, 0.3, 2 );
    var geometry = new THREE.ShapeGeometry( shapes );
    geometry.computeBoundingBox();
    xMid = 0.5 * ( geometry.boundingBox.max.x - geometry.boundingBox.min.x );
    geometry.translate( -xMid, 0, 0 );
    // make shape ( N.B. edge view not visible )
    textShape.fromGeometry( geometry );
    text = new THREE.Mesh( textShape, matLite );
    text.position.z = maxR;
    scene.add( text );

    // // make outline shape ( N.B. edge view remains visible )
    // var holeShapes = [];
    // for ( var i = 0; i < shapes.length; i ++ ) {
        // var shape = shapes[ i ];
        // if ( shape.holes && shape.holes.length > 0 ) {
            // for ( var j = 0; j < shape.holes.length; j ++ ) {
                // var hole = shape.holes[ j ];
                // holeShapes.push( hole );
            // }
        // }
    // }
    // shapes.push.apply( shapes, holeShapes );
    // var lineText = new THREE.Object3D();
    // for ( var i = 0; i < shapes.length; i ++ ) {
        // var shape = shapes[ i ];
        // var points = shape.getPoints();
        // var geometry = new THREE.BufferGeometry().setFromPoints( points );
        
        // geometry.translate( xMid, 0, 0 );
        // var lineMesh = new THREE.Line( geometry, matDark );
        // lineText.add( lineMesh );
    // }
    // scene.add( lineText );
}

/** Compute normal, centroid, radius, etc. for cell. */
function computeCell(cell) {
	cell.normal = computeNormal(cell);
	cell.centroid = computeCentroid(cell);
	// cell.radius = computeRadius(cell);
}

/** Return normal vector of cell. */
function computeNormal(cell) {
	var a = board.vertices[cell[0]],
		b = board.vertices[cell[1]],
        c = board.vertices[cell[2]];
    console.log("a b c:", a, b, c);
    // u = a - b; v = c - b
    var u = new THREE.Vector3().subVectors(a, b),
        v = new THREE.Vector3().subVectors(c, b);
    // u = u x v (is that the wrong order?)
    u.cross(v);
    u.normalize(); 
    console.log("Normal:", u);   
	return u;
}

/** Return centroid point of cell. */
function computeCentroid(cell) {
    // One approach would be https://gist.github.com/AndrewRayCode/c9c41b549d0b1e97da8890a79e3ab8d0,
    // which is based on Three.js "faces", i.e. triangles/quads into which a geometry is subdivided.
    // But it's not clear how that will contribute to finding the centroid of whole cell (polygon);
    // I would have to be able to map cells to geometry faces.

    // https://math.stackexchange.com/a/1345/2656
    // First we need two orthogonal vectors in the plane of the polygon, e1 and e2.
    if (!cell.normal) cell.normal = computeNormal(cell);  
    var e1 = new THREE.Vector3().subVectors(board.vertices[cell[0]], board.vertices[cell[1]]);
    var e2 = new THREE.Vector3().crossVectors(e1, cell.normal);
    console.log(e1, e2);

    // Actually, it may be easier to use the algorithms at https://stackoverflow.com/questions/2355931/compute-the-centroid-of-a-3d-planar-polygon/2360507#2360507
    // by tom10 and kennytm. But I'll try to finish the above one.

    return ;
}

function reportProgress(xhr) {
    console.log("Loading progress", xhr.loaded, xhr.total);
    // TODO: display spinner?
}

function loadingError() {
    console.log("loadingError");
    // TODO: Tell user?
}
