// Next dev steps:
// x load/parse phe-C200stI_1.json;
// x script to convert .obj to .json format.
/*
    Operations needed:
    - Import geometry from source into THREE.js structures (LineSegments, mesh, Dots?)
    - Import geometry from source into program data structures (possibly a halfedge DS?)
    - Display edges
    - Display faces, including numbers
    - Display vertices (as billboard circles? glowing stars?)
    - Pick an edge with mouse
    - Pick a face
    - Pick a vertex
    - Change a vertex from one material to another; that apparently means
      moving it from one LineSegments to another.
*/

var MAX_POINTS = 1000, MAX_EDGES = 1000, MAX_FACES = 1000;
var dataURL = 'data/testCube.json'; // 'phe-C200stI_1.json';
var DEFAULT_DATA_FILE='data/phe-T.json';

var sphere;


// TODO: make antialias a controllable option?
var renderer = new THREE.WebGLRenderer({antialias:  true});
renderer.setSize( 800, 600 );
document.body.appendChild( renderer.domElement );

var scene = new THREE.Scene();

var camera = new THREE.PerspectiveCamera(
    35,             // Field of view
    800 / 600,      // Aspect ratio
    0.1,            // Near plane
    10000           // Far plane
);
camera.position.set( 15, 10, 15 );
camera.lookAt( scene.position );

var light = new THREE.PointLight( 0xFFFF00 );
light.position.set( 10, 10, 10 );
scene.add( light );

renderer.setClearColor( 0, 1);
renderer.render( scene, camera );

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

fetch(DEFAULT_DATA_FILE)
  .then(status)
  .then(json)
  .then(function(data) {
    console.log('Request succeeded with JSON response', data);
    importData(data);
  }).catch(function(error) {
    console.log('Request failed', error);
  });

/** Pull data into Three.js and app data structures. */
function importData(data) {
    // // geometry
    // var geometry = new THREE.BufferGeometry();

    // // attributes
    // var positions = new Float32Array( MAX_POINTS * 3 ); // 3 vertices per point
    // geometry.addAttribute( 'position', new THREE.BufferAttribute( positions, 3 ) );
    var geometry = new THREE.Geometry();
    
    // TODO: This will add each edge twice. Remove one of them.
    for (var f=0; f < data.faces.length; f++) {
        var face = data.faces[f];
        for (var v=0; v < face.length; v++) {
            var nv = (v+1 >= face.length) ? 0 : v+1;
            var vx = data.vertices[face[v]];
            geometry.vertices.push(new THREE.Vector3(vx[0], vx[1], vx[2]));
            // was: new (Function.prototype.bind.apply(THREE.Vector3, data.vertices[face[v]-1])));
            var vx = data.vertices[face[nv]];
            geometry.vertices.push(new THREE.Vector3(vx[0], vx[1], vx[2]));
            // was: new (Function.prototype.bind.apply(THREE.Vector3, data.vertices[face[nv]-1])));
        }
    }

    var material = new THREE.LineBasicMaterial( { color: 0xddddff, linewidth: 2 } );
    sphere = new THREE.LineSegments( geometry, material );

    scene.add(sphere);
}

function animate() {
    // cube.rotation.x += 0.1; cube.rotation.y += 0.1;
    // lineSegs.rotation.y += 0.07;
    if (sphere !== undefined) {
        sphere.rotation.x += 0.01;
        sphere.rotation.y += 0.01;
        // console.log("Rotated");
    }
    requestAnimationFrame( animate );
    renderer.render( scene, camera );
}

animate();