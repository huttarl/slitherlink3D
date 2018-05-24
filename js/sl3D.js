/*
    Operations needed:
    x Load/parse json mesh data
    x Separate script to convert .obj to .json format
    x Camera smooth zoom after mesh loaded.
    x Import geometry from source into THREE.js structures (LineSegments, mesh, Dots?)
    - Import geometry from source into program data structures (possibly a halfedge DS?)
    x Display edges
      x Don't display them twice.
      - Display them wider? If so, probably use https://github.com/spite/THREE.MeshLine
    - Display faces, including numbers!
    - Display vertices (as billboard circles? glowing stars?)
    - Pick an edge with mouse
    - Pick a face
    - Pick a vertex
    - Change an edge from one material to another; that apparently means
      having to move it from one LineSegments to another. UNLESS... we can do
      it by changing its texture coordinates. Can we do that with THREE.MeshLine?

      OK, I found that for faces, Geometry has a .faceVertexUvs property
      (https://threejs.org/docs/index.html#api/core/Geometry.faceVertexUvs),
      which allows you
      you to specify texture coordinates for each vertex on each face.
      This will let us basically specify a color for each face.

      The .colors property allows you to specify a color per vertex,
      which can't be used for faces but should do the trick for LineSegments.
      It should also work for MeshLine, but remember MeshLineMaterial.map and .useMap.
    - Come up with a sample puzzle to test with.
    - Display a "loading" spinner while loading?
*/

var MAX_POINTS = 1000, MAX_EDGES = 1000, MAX_FACES = 1000;

// Mesh to load. Points are assumed to be centered around origin.
var dataURL = 'data/';
var DEFAULT_DATA_FILE='phe-A200sC200tI.json';

var renderer, scene, camera, sphere;

var maxR = 1; // max distance from origin.
var maxR2 = 0; // maxR squared
var camR = 4 * maxR; // distance of camera
var autoRotating = true;

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

    renderer.setClearColor( 0, 1);
    render();

    window.addEventListener( 'resize', onWindowResize, false );

    fetch(dataURL + DEFAULT_DATA_FILE)
      .then(status)
      .then(json)
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

function json(response) {
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
    // // geometry
    // var geometry = new THREE.BufferGeometry();

    // // attributes
    // var positions = new Float32Array( MAX_POINTS * 3 ); // 3 vertices per point
    // geometry.addAttribute( 'position', new THREE.BufferAttribute( positions, 3 ) );
    var geometry = new THREE.Geometry();
    
    maxR2 = 0;

    var edgesAddedToMesh = {};

    for (var f=0; f < data.faces.length; f++) {
        var face = data.faces[f];
        for (var v=0; v < face.length; v++) {
            var nv = (v+1 >= face.length) ? 0 : v+1;
            // Check: is the reversed edge already added? If so don't add it again.
            if ([face[nv], face[v]] in edgesAddedToMesh) {
                // console.log("Edge already added", face[v], face[nv]);
                continue;
            }
            // Add this edge.
            edgesAddedToMesh[[face[v], face[nv]]] = true;

            var v1 = data.vertices[face[v]], v2 = data.vertices[face[nv]];
            updateMaxR(v1);
            geometry.vertices.push(new THREE.Vector3(v1[0], v1[1], v1[2]));
            // was: new (Function.prototype.bind.apply(THREE.Vector3, data.vertices[face[v]-1])));
            updateMaxR(v2);
            geometry.vertices.push(new THREE.Vector3(v2[0], v2[1], v2[2]));
            // was: new (Function.prototype.bind.apply(THREE.Vector3, data.vertices[face[nv]-1])));
        }
    }

    maxR = Math.sqrt(maxR2);
    console.log("maxR: ", maxR);

    var material = new THREE.LineBasicMaterial( { color: 0xff888888, linewidth: 6 } ); // 0xff888888
    sphere = new THREE.LineSegments( geometry, material );

    scene.add(sphere);

    autoRotating = true; // autorotate at first
}

/** Linear interpolation */
// Precise method, which guarantees v = v1 when t = 1.
// https://en.wikipedia.org/wiki/Linear_interpolation#Programming_language_support
function lerp(v0, v1, t) {
    return (1 - t) * v0 + t * v1;
}

function animate() {
    if (autoRotating && sphere !== undefined) {
        sphere.rotation.x += 0.0005;
        sphere.rotation.y += 0.0005;
        // console.log("Rotated");
    }

    camR = lerp(camR, 4 * maxR, 0.15);
    // camera.position.set( camR, 0, 0 );
    // camera.lookAt( scene.position );

    // console.log("animate");
    requestAnimationFrame( animate );
    controls.update();
    // not needed?
    render();
}

function render() {
    console.log("render");
    renderer.render( scene, camera );
}

function changeControls() {
    console.log("changeControls");
    // Stop autorotating when user touches controls.
    autoRotating = false;
    render();
}
init();
animate();
