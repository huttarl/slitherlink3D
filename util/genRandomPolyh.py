#!/usr/bin/env python3.11
"""Generate random polyhedra, for use in Slitherlink3D puzzles.
I used Claude to draft the code.

Usage: util/genRandomPolyh.py [n] [--name NAME] [--out FILE] [--spiral]
                             [--no-quads] [--angle DEG] [--quiet]
See usage() for what each one does, and main() for the defaults.

Two ways to place the points:
random with repulsion (the default): start with random points on a sphere, then
spread them out evenly by simulating repulsion.
--spiral: use a golden spiral to lay out points evenly (yields more quads around
the equator).

We then to convert to a polyhedron by computing the convex hull, then merge almost-coplanar
adjacent triangles into quads. The resulting mesh is exported to OBJ format, which
util/obj2json.py turns into a grid file -- so pass --name to give each solid its
own gridId.

The shebang selects python3.11, the interpreter carrying numpy/scipy/matplotlib.
"""

import random
import sys

import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial import ConvexHull

# Our local modules: the polar dual from the Goldberg generator, and the general
# coplanar-facet merge from the uniform one. Both are already exercised by the
# grids in data/, so the methods below inherit machinery that is known to work.
from genGoldberg import polar_dual
from genUniformPolyh import merge_coplanar_faces

# How far to spread the points by default: some, but not all the way. Fully
# relaxed points are so even that every vertex degree comes out 5 or 6, which
# (in the --dual method) means every face is a pentagon or hexagon; unrelaxed
# points give a wider mix of face sizes but clump. Halfway keeps some of both.
DEFAULT_RELAX = 0.5

# --seeds wants more than that, and can afford it. Relaxation only spreads the
# seed CENTRES there, and the seed sizes are drawn independently, so unlike
# --dual it costs nothing in face variety -- while unevenly spaced seeds leave
# sliver triangles in the gaps between them. Measured over 6 solids per setting
# at n=30, the sharpest corner any face had: 19 degrees at relax 0.5, 23 at 0.75,
# 27 at 0.9, and no better at 1.0.
DEFAULT_SEEDS_RELAX = 0.9

# How much of the room between neighbouring seeds a seed polygon takes up, in
# the --seeds method. Under 1 so that no two seeds touch, which is what keeps
# each of them a face of the hull -- and well under, because seeds that nearly
# touch squeeze the filler triangles between them into slivers. From the same
# measurements: median sharpest corner 27 degrees at 0.7, 21 at 0.8, and 8 at
# 0.97, where some faces became unusable splinters.
SEED_FILL = 0.7

# The shortest edge the --dual method will leave alone, as a fraction of the
# median edge length. The dual puts a vertex at each triangle's pole, and two
# nearly coplanar triangles have poles almost on top of each other -- which draws
# as a single blob, since a vertex sphere's radius is a third of a typical edge
# (see VERTEX_RADIUS and EDGE_RADIUS in js/constants.js). Measured on one such
# solid: 5 of its 84 edges came out under 0.10 with a median of 0.38, the worst
# at 0.015. See separate_short_edges.
MIN_EDGE_FRACTION = 0.4


def generate_random_points_on_sphere(n, radius=1.0):
    """
    Generate n random points uniformly distributed on the surface of a sphere.

    Uses the Fibonacci sphere algorithm for better uniform distribution,
    or alternatively uses spherical coordinates with proper distribution.

    Args:
        n: Number of points to generate
        radius: Radius of the sphere (default: 1.0)

    Returns:
        numpy array of shape (n, 3) containing the 3D coordinates
    """
    points = []

    # Using spherical coordinates with uniform distribution
    # phi (azimuthal angle): uniform in [0, 2π]
    # theta (polar angle): arccos(uniform in [-1, 1]) for uniform distribution on sphere

    for i in range(n):
        # Generate uniformly distributed points on sphere surface
        u = np.random.uniform(0, 1)
        v = np.random.uniform(0, 1)

        theta = 2 * np.pi * u  # azimuthal angle
        phi = np.arccos(2 * v - 1)  # polar angle

        # Convert spherical to Cartesian coordinates
        x = radius * np.sin(phi) * np.cos(theta)
        y = radius * np.sin(phi) * np.sin(theta)
        z = radius * np.cos(phi)

        points.append([x, y, z])

    return np.array(points)


def simulate_repulsion(points, radius=1.0, max_iterations=1000,
                       force_strength=0.1, max_force=1.0,
                       damping=0.9, max_velocity=0.1,
                       convergence_threshold=1e-4, animate=False, update_interval=10):
    """
    Simulate electrostatic repulsion between points on sphere surface.

    Args:
        points: Initial points (n, 3)
        radius: Sphere radius
        max_iterations: Maximum simulation steps
        force_strength: Strength of repulsive force
        max_force: Cap on force magnitude to prevent instability
        damping: Velocity damping factor (0-1, lower = more damping)
        max_velocity: Cap on velocity magnitude
        convergence_threshold: Stop when total movement falls below this
        animate: If True, display real-time animation
        update_interval: Update display every N iterations

    Returns:
        Adjusted points on sphere surface
    """
    points = points.copy()
    n = len(points)
    velocities = np.zeros_like(points)

    # Set up animation if requested
    if animate:
        plt.ion()  # Turn on interactive mode
        fig = plt.figure(figsize=(10, 10))
        ax = fig.add_subplot(111, projection='3d')

        # Draw wireframe sphere for reference
        u = np.linspace(0, 2 * np.pi, 30)
        v = np.linspace(0, np.pi, 20)
        x = radius * np.outer(np.cos(u), np.sin(v))
        y = radius * np.outer(np.sin(u), np.sin(v))
        z = radius * np.outer(np.ones(np.size(u)), np.cos(v))

        ax.plot_wireframe(x, y, z, color='lightblue', alpha=0.2, linewidth=0.5)

        # Initialize scatter plot
        scatter = ax.scatter(points[:, 0], points[:, 1], points[:, 2],
                            c='gray', marker='o', s=40, alpha=0.8)

        # Set labels and limits
        ax.set_xlabel('X')
        ax.set_ylabel('Y')
        ax.set_zlabel('Z')
        max_range = radius * 1.1
        ax.set_xlim([-max_range, max_range])
        ax.set_ylim([-max_range, max_range])
        ax.set_zlim([-max_range, max_range])

        # Force equal aspect ratio for all axes
        ax.set_box_aspect([1, 1, 1])

        title = ax.set_title('Repulsion Simulation - Iteration 0')
        plt.show()

    for iteration in range(max_iterations):
        forces = np.zeros_like(points)

        # Calculate repulsive forces between all pairs
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue

                # Vector from j to i
                diff = points[i] - points[j]
                distance = np.linalg.norm(diff)

                if distance < 1e-10:  # Avoid division by zero
                    continue

                # Inverse square law force
                force_magnitude = force_strength / (distance ** 2)

                # Cap the force to prevent instability
                force_magnitude = min(force_magnitude, max_force)

                # Force direction (normalized)
                force_direction = diff / distance

                # Add to total force on particle i
                forces[i] += force_magnitude * force_direction

        # Project forces onto tangent plane of sphere at each point
        for i in range(n):
            # Normal vector at point i (pointing outward from sphere center)
            normal = points[i] / np.linalg.norm(points[i])

            # Project force onto tangent plane (remove normal component)
            force_tangent = forces[i] - np.dot(forces[i], normal) * normal
            forces[i] = force_tangent

        # Update velocities with damping
        velocities = damping * velocities + forces

        # Cap velocities
        for i in range(n):
            speed = np.linalg.norm(velocities[i])
            if speed > max_velocity:
                velocities[i] = velocities[i] * (max_velocity / speed)

        # Update positions
        points += velocities

        # Project points back onto sphere surface
        for i in range(n):
            points[i] = radius * points[i] / np.linalg.norm(points[i])

        # Check for convergence
        max_movement = np.max(np.linalg.norm(velocities, axis=1))

        if iteration % 100 == 0:
            print(f"Iteration {iteration}: max movement = {max_movement:.6f}")

        # Update display if animating
        if animate and iteration % update_interval == 0:
            scatter._offsets3d = (points[:, 0], points[:, 1], points[:, 2])
            title.set_text(f'Repulsion Simulation - Iteration {iteration}')
            fig.canvas.draw()
            fig.canvas.flush_events()

        if max_movement < convergence_threshold:
            print(f"Converged after {iteration} iterations (max movement = {max_movement:.6f})")
            if animate:
                # Final update
                scatter._offsets3d = (points[:, 0], points[:, 1], points[:, 2])
                title.set_text(f'Repulsion Simulation - Converged at iteration {iteration}')
                fig.canvas.draw()
                fig.canvas.flush_events()
                plt.ioff()  # Turn off interactive mode
                plt.close(fig)
            break
    else:
        print(f"Reached max iterations ({max_iterations})")
        if animate:
            plt.ioff()
            plt.close(fig)

    return points


def visualize_points_on_sphere(points, radius=1.0, hull=None):
    """
    Visualize points on a sphere using matplotlib.

    Args:
        points: numpy array of shape (n, 3) with point coordinates
        radius: radius of the sphere for reference wireframe
        hull: optional ConvexHull object to display the polyhedron
    """
    fig = plt.figure(figsize=(10, 10))
    ax = fig.add_subplot(111, projection='3d')

    # Plot the points
    ax.scatter(points[:, 0], points[:, 1], points[:, 2],
               c='gray', marker='o', s=100, alpha=0.8, label='Vertices')

    # Draw convex hull if provided
    if hull is not None:
        # Draw edges of the convex hull
        for simplex in hull.simplices:
            # Each simplex is a triangular face with 3 vertex indices
            # Draw the three edges of the triangle
            for i in range(3):
                start = points[simplex[i]]
                end = points[simplex[(i + 1) % 3]]
                ax.plot([start[0], end[0]],
                       [start[1], end[1]],
                       [start[2], end[2]],
                       'b-', linewidth=1, alpha=0.6)

    # Draw a wireframe sphere for reference
    u = np.linspace(0, 2 * np.pi, 30)
    v = np.linspace(0, np.pi, 20)
    x = radius * np.outer(np.cos(u), np.sin(v))
    y = radius * np.outer(np.sin(u), np.sin(v))
    z = radius * np.outer(np.ones(np.size(u)), np.cos(v))

    ax.plot_wireframe(x, y, z, color='lightblue', alpha=0.2, linewidth=0.5)

    # Set labels and title
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')
    title = f'{len(points)} Points on Unit Sphere'
    if hull is not None:
        title += f'\nConvex Hull: {len(hull.simplices)} faces, {len(hull.vertices)} vertices'
    ax.set_title(title)

    # Set equal aspect ratio
    max_range = radius * 1.1
    ax.set_xlim([-max_range, max_range])
    ax.set_ylim([-max_range, max_range])
    ax.set_zlim([-max_range, max_range])
    
    # Force equal aspect ratio for all axes
    ax.set_box_aspect([1, 1, 1])

    ax.legend()

    plt.show()


def find_coplanar_triangles(hull, angle_threshold_deg=5.0):
    """
    Find pairs of adjacent triangles that are nearly coplanar.
    
    Args:
        hull: ConvexHull object
        angle_threshold_deg: maximum angle deviation (in degrees) to consider coplanar
    
    Returns:
        List of (face_idx1, face_idx2) tuples for coplanar pairs
    """
    coplanar_pairs = []
    angle_threshold = np.cos(np.radians(angle_threshold_deg))
    
    for i, neighbors in enumerate(hull.neighbors):
        for j in neighbors:
            if j > i:  # Only check each pair once
                # Get normal vectors from plane equations
                normal_i = hull.equations[i][:3]
                normal_j = hull.equations[j][:3]
                
                # Check if normals are nearly parallel (dot product close to ±1)
                dot_product = abs(np.dot(normal_i, normal_j))
                if dot_product > angle_threshold:
                    coplanar_pairs.append((i, j))
    
    return coplanar_pairs


def order_quad_vertices(tri1, tri2, points):
    """
    Order 4 vertices from two triangles sharing an edge into a proper convex quad.
    
    Args:
        tri1, tri2: arrays of 3 vertex indices each
        points: vertex coordinates array
    
    Returns:
        Array of 4 vertex indices ordered for a convex quad, or None if invalid
    """
    # Find shared edge (2 common vertices)
    common = set(tri1) & set(tri2)
    if len(common) != 2:
        return None
    
    # Find the unique vertices (one per triangle)
    unique1 = (set(tri1) - common).pop()
    unique2 = (set(tri2) - common).pop()
    shared = list(common)
    
    # We need to order vertices as: unique1 -> shared_a -> unique2 -> shared_b
    # such that we traverse the quad boundary in order
    
    # Find which shared vertex is adjacent to unique1 in tri1
    # Triangles are ordered, so we look at the edges
    tri1_list = list(tri1)
    
    # Find position of unique1 in tri1
    idx_unique1 = tri1_list.index(unique1)
    
    # The two adjacent vertices in tri1 are the shared vertices
    # Get them in the order they appear relative to unique1
    shared_a = tri1_list[(idx_unique1 + 1) % 3]
    shared_b = tri1_list[(idx_unique1 + 2) % 3]
    
    # Order the quad: unique1, shared_a, unique2, shared_b
    quad = np.array([unique1, shared_a, unique2, shared_b])
    
    # Verify the quad is convex by checking that all cross products point the same direction
    if not is_quad_convex(quad, points):
        # Try the other ordering
        quad = np.array([unique1, shared_b, unique2, shared_a])
        if not is_quad_convex(quad, points):
            return None
    
    return quad


def project_quad_to_plane(quad_indices, points):
    """
    Adjust quad vertices to make them exactly coplanar by projecting onto best-fit plane.
    
    Args:
        quad_indices: array of 4 vertex indices
        points: vertex coordinates array (will be modified in place)
    
    Returns:
        None (modifies points in place)
    """
    # Get the 4 vertices
    quad_verts = points[quad_indices]
    
    # Compute centroid
    centroid = np.mean(quad_verts, axis=0)
    
    # Center the vertices
    centered = quad_verts - centroid
    
    # Compute best-fit plane using SVD
    # The plane normal is the singular vector with smallest singular value
    (_, _, vh) = np.linalg.svd(centered)
    normal = vh[2, :]  # Last row of V^T is the normal to the best-fit plane
    
    # Project each vertex onto the plane
    for i, idx in enumerate(quad_indices):
        # Vector from centroid to vertex
        v = points[idx] - centroid
        
        # Remove component perpendicular to plane
        v_projected = v - np.dot(v, normal) * normal
        
        # Update vertex position (projected point)
        points[idx] = centroid + v_projected
    
    # Re-normalize vertices to lie on unit sphere
    for idx in quad_indices:
        points[idx] = points[idx] / np.linalg.norm(points[idx])


def is_quad_convex(quad, points):
    """
    Check if a quad is convex by verifying all cross products point outward.
    
    Args:
        quad: array of 4 vertex indices
        points: vertex coordinates
    
    Returns:
        True if the quad is convex
    """
    # Get the 4 vertices
    v = points[quad]
    
    # Compute normal at each vertex using cross product of adjacent edges
    normals = []
    for i in range(4):
        v1 = v[(i + 1) % 4] - v[i]
        v2 = v[(i - 1) % 4] - v[i]
        normal = np.cross(v1, v2)
        normals.append(normal)
    
    # Check if all normals point in roughly the same direction
    reference = normals[0]
    for normal in normals[1:]:
        if np.dot(reference, normal) < 0:
            return False
    
    return True


def orient_face_outward(face, points):
    """Return the face's vertex indices wound counterclockwise as seen from
    outside the solid — i.e., so the right-hand-rule normal points outward.

    Assumes the solid is convex and contains the origin, which holds for our
    hulls of points on the unit sphere: then a face is correctly wound iff
    its normal points away from the origin (has positive dot product with
    the face centroid). If the winding is already outward the face is
    returned unchanged, otherwise reversed.

    Why this matters: scipy's ConvexHull.simplices do NOT have consistent
    orientation, and the quad-merge step inherits that arbitrary winding.
    Mixed winding breaks halfedge-based mesh libraries downstream — e.g.,
    COMPAS (used by genSliPuzzles.py) returns empty face_neighbors() for
    inconsistently wound faces, crashing puzzle generation.

    Args:
        face: sequence of vertex indices (triangle or near-planar quad)
        points: vertex coordinates array

    Returns:
        List of the vertex indices, in outward-wound order.
    """
    verts = points[np.array(face)]
    centroid = verts.mean(axis=0)
    # For a triangle or near-planar convex quad, the cross product of the
    # first two edges is a good-enough face normal.
    normal = np.cross(verts[1] - verts[0], verts[2] - verts[0])
    if np.dot(normal, centroid) < 0:
        return list(reversed(list(face)))
    return list(face)


def merge_coplanar_triangles_to_quads(hull, points, angle_threshold_deg=5.0, adjust_vertices=False):
    """
    Merge coplanar adjacent triangles into quadrilateral faces.
    
    Args:
        hull: ConvexHull object
        points: vertex coordinates (may be modified if adjust_vertices=True)
        angle_threshold_deg: maximum angle deviation to consider coplanar
        adjust_vertices: if True, project quad vertices onto best-fit plane
    
    Returns:
        faces: list of faces, where each face is a list of vertex indices
               (can be triangles or quads)
    """
    print(f"\nMerging coplanar triangles (angle threshold: {angle_threshold_deg}°)...")
    
    # Find all coplanar pairs
    coplanar_pairs = find_coplanar_triangles(hull, angle_threshold_deg)
    print(f"Found {len(coplanar_pairs)} coplanar triangle pairs")
    
    # Track which triangles have been merged
    merged = set()
    faces = []
    quads_created = []
    
    # Process coplanar pairs
    for face_i, face_j in coplanar_pairs:
        if face_i in merged or face_j in merged:
            continue
        
        tri1 = hull.simplices[face_i]
        tri2 = hull.simplices[face_j]
        
        # Try to merge into a quad
        quad = order_quad_vertices(tri1, tri2, points)
        
        if quad is not None:
            faces.append(orient_face_outward(quad, points))
            merged.add(face_i)
            merged.add(face_j)
            quads_created.append(quad)

    # Add remaining triangles that weren't merged
    for i, simplex in enumerate(hull.simplices):
        if i not in merged:
            faces.append(orient_face_outward(simplex, points))
    
    # Optionally adjust vertices to make quads exactly coplanar
    if adjust_vertices and quads_created:
        print(f"Adjusting {len(quads_created)} quads to be exactly coplanar...")
        for quad in quads_created:
            project_quad_to_plane(np.array(quad), points)
    
    # Count face types
    num_triangles = sum(1 for f in faces if len(f) == 3)
    num_quads = sum(1 for f in faces if len(f) == 4)
    
    print(f"Result: {num_triangles} triangles, {num_quads} quads (total {len(faces)} faces)")
    
    return faces


def visualize_mesh(points, faces, radius=1.0):
    """
    Visualize a mesh with mixed triangle and quad faces.
    
    Args:
        points: numpy array of shape (n, 3) with vertex coordinates
        faces: list of faces, where each face is a list of vertex indices
        radius: radius of the sphere for reference wireframe
    """
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    
    fig = plt.figure(figsize=(10, 10))
    ax = fig.add_subplot(111, projection='3d')
    
    # Separate triangles and quads for different coloring
    triangle_faces = []
    quad_faces = []
    
    for face in faces:
        face_vertices = points[face]
        if len(face) == 3:
            triangle_faces.append(face_vertices)
        elif len(face) == 4:
            quad_faces.append(face_vertices)
    
    # Draw triangles as filled polygons
    if triangle_faces:
        tri_collection = Poly3DCollection(triangle_faces, 
                                         facecolors='lightblue', 
                                         edgecolors='blue', 
                                         linewidths=1.5, 
                                         alpha=0.8)
        ax.add_collection3d(tri_collection)
    
    # Draw quads as filled polygons
    if quad_faces:
        quad_collection = Poly3DCollection(quad_faces, 
                                          facecolors='lightgreen', 
                                          edgecolors='darkgreen', 
                                          linewidths=2, 
                                          alpha=0.8)
        ax.add_collection3d(quad_collection)
    
    # Plot the vertices
    ax.scatter(points[:, 0], points[:, 1], points[:, 2],
               c='gray', marker='o', s=30, alpha=1.0, label='Vertices',
               depthshade=True, # doesn't seem to help
               zorder=-1, # was 10
               )
    
    # # Draw a wireframe sphere for reference
    # u = np.linspace(0, 2 * np.pi, 30)
    # v = np.linspace(0, np.pi, 20)
    # x = radius * np.outer(np.cos(u), np.sin(v))
    # y = radius * np.outer(np.sin(u), np.sin(v))
    # z = radius * np.outer(np.ones(np.size(u)), np.cos(v))
    #
    # ax.plot_wireframe(x, y, z, color='gray', alpha=0.1, linewidth=0.5)
    
    # Set labels and title
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')
    triangle_count = len(triangle_faces)
    quad_count = len(quad_faces)
    title = f'{len(points)} Vertices\n{triangle_count} Triangles (blue), {quad_count} Quads (green)'
    ax.set_title(title)
    
    # Set equal aspect ratio
    max_range = radius * 1.1
    ax.set_xlim([-max_range, max_range])
    ax.set_ylim([-max_range, max_range])
    ax.set_zlim([-max_range, max_range])
    
    # Force equal aspect ratio for all axes
    ax.set_box_aspect([1, 1, 1])
    
    ax.legend()
    
    plt.show()


def export_mesh_to_obj(points, faces, filename='polyhedron.obj',
                       group='polyhedron'):
    """
    Export a mesh with mixed triangle and quad faces to Wavefront OBJ format.

    Args:
        points: numpy array of shape (n, 3) with vertex coordinates
        faces: list of faces, where each face is a list of vertex indices
        filename: output filename (default: 'polyhedron.obj')
        group: the OBJ group name, which obj2json.py turns into the grid's
            gridId/gridName -- so give each solid its own
    """
    with open(filename, 'w') as f:
        f.write("# Polyhedron with triangles and quads\n")
        f.write(f"g {group}\n")
        f.write("# vertices\n")
        
        # Write all vertices
        for point in points:
            f.write(f"v {point[0]} {point[1]} {point[2]}\n")
        
        f.write("# faces\n")
        
        # Write all faces (can be triangles or quads)
        # Note: OBJ format uses 1-based indexing
        for face in faces:
            face_str = ' '.join(str(idx + 1) for idx in face)
            f.write(f"f {face_str}\n")
    
    num_triangles = sum(1 for f in faces if len(f) == 3)
    num_quads = sum(1 for f in faces if len(f) == 4)
    
    print(f"\nExported mesh to {filename}")
    print(f"  Vertices: {len(points)}")
    print(f"  Faces: {len(faces)} ({num_triangles} triangles, {num_quads} quads)")


def generate_golden_spiral(n):
    indices = np.arange(0, n, dtype=float) + 0.5

    phi = np.arccos(1 - 2 * indices / n)      # arccos(1 to -1) = 0 to 2π
    theta = np.pi * (1 + 5 ** 0.5) * indices  # golden angle increments

    points = np.empty((n, 3))
    points[:, 0] = np.cos(theta) * np.sin(phi)
    points[:, 1] = np.sin(theta) * np.sin(phi)
    points[:, 2] = np.cos(phi)

    return points


def usage():
    print('Usage: util/genRandomPolyh.py [n] [--dual|--seeds] [--name NAME] '
          '[--out FILE] [--relax T] [--spiral] [--no-quads] [--angle DEG] '
          '[--quiet]', file=sys.stderr)
    print('  n           number of vertices (default 70); the hull then has '
          '2n-4 faces and 3n-6 edges, fewer once quads are merged. With --dual '
          'it is the number of FACES instead (3n-6 edges, 2n-4 vertices)',
          file=sys.stderr)
    print('  --dual      dual of the hull: one face per point, no triangles at '
          'all, sizes following the points\' degrees', file=sys.stderr)
    print('  --seeds     scatter regular polygons (3 to 6 sides) and let the '
          'hull triangulate the gaps between them', file=sys.stderr)
    print(f'  --relax     how evenly to spread the points, 0 to 1 (default '
          f'{DEFAULT_RELAX}, or {DEFAULT_SEEDS_RELAX} with --seeds): 0 leaves '
          f'them clumped and the face sizes varied, 1 spreads them evenly and '
          f'narrows the sizes', file=sys.stderr)
    print(f'  --min-edge  with --dual, the shortest edge to allow as a fraction '
          f'of the median (default {MIN_EDGE_FRACTION}; 0 to leave them alone)',
          file=sys.stderr)
    print('  --name      OBJ group name, which obj2json.py turns into the '
          "grid's gridId/gridName (default 'polyhedron')", file=sys.stderr)
    print('  --out       output OBJ path (default polyhedron_with_quads.obj, '
          'or polyhedron_triangulated.obj with --no-quads)', file=sys.stderr)
    print('  --spiral    place points on a golden spiral instead of randomly '
          'with repulsion', file=sys.stderr)
    print('  --no-quads  leave the hull triangulated', file=sys.stderr)
    print('  --angle     how near coplanar two triangles must be to merge, in '
          'degrees (default 5)', file=sys.stderr)
    print('  --quiet     no matplotlib animation or window -- for scripted '
          'runs', file=sys.stderr)
    sys.exit(1)


def main():
    """Parse the arguments and write one random polyhedron.

    Arguments rather than the edited-by-hand settings this used to have: making
    three grids of different sizes meant three edits, and an edited default is
    a poor record of what produced a file.
    """
    args = sys.argv[1:]
    # --relax starts as None so that a method can pick its own default; see
    # DEFAULT_SEEDS_RELAX for why --seeds wants a different one.
    options = {'--name': 'polyhedron', '--out': None, '--angle': '5.0',
               '--relax': None, '--min-edge': str(MIN_EDGE_FRACTION)}
    flags = {'--spiral': False, '--no-quads': False, '--quiet': False,
             '--dual': False, '--seeds': False}
    n = 70
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in flags:
            flags[arg] = True
        elif arg in options:
            i += 1
            if i >= len(args):
                print(f'{arg} needs a value.', file=sys.stderr)
                usage()  # exits
            options[arg] = args[i]
        elif arg.startswith('-'):
            print(f"Unrecognized option '{arg}'.", file=sys.stderr)
            usage()  # exits
        else:
            n = int(arg)
        i += 1
    if n < 4:
        print('At least 4 vertices are needed for a polyhedron.', file=sys.stderr)
        sys.exit(1)

    # A scripted run wants no windows and no animation: with the Agg backend the
    # animation is wasted work, and plt.show() would block a GUI backend forever.
    animate = not flags['--quiet']
    merge_quads = not flags['--no-quads']
    relax = (float(options['--relax']) if options['--relax'] is not None
             else (DEFAULT_SEEDS_RELAX if flags['--seeds'] else DEFAULT_RELAX))
    if flags['--dual'] and flags['--seeds']:
        print('--dual and --seeds are two different methods; pick one.',
              file=sys.stderr)
        sys.exit(1)
    out = options['--out'] or ('polyhedron_with_quads.obj' if merge_quads
                               else 'polyhedron_triangulated.obj')

    # The two methods that produce faces other than triangles hand back their own
    # (vertices, faces) and are done: no quad merging, no separate hull step.
    # (--seeds places its own points, one batch of centres rather than n
    # vertices, so it does its own scattering.)
    if flags['--dual'] or flags['--seeds']:
        if flags['--dual']:
            points = (generate_golden_spiral(n) if flags['--spiral']
                      else relaxed_points(n, relax, animate))
            (vertices, faces) = dual_of_triangulation(
                points, float(options['--min-edge']))
        else:
            (vertices, faces) = seeded_solid(n, relax, animate)
        export_mesh_to_obj(vertices, faces, out, group=options['--name'])
        if animate:
            visualize_mesh(vertices, faces, radius=1.0)
        return

    points = (generate_golden_spiral(n) if flags['--spiral']
              else relaxed_points(n, relax, animate))

    # Compute convex hull
    print("\nComputing convex hull...")
    hull = ConvexHull(points)

    print(f"Convex hull has {len(hull.vertices)} vertices and {len(hull.simplices)} faces")
    print(f"All vertices are on hull: {len(hull.vertices) == n}")

    if merge_quads:
        # Merge coplanar triangles into quads. adjust_vertices projects each
        # quad's corners onto their best-fit plane, so the face is exactly flat.
        faces = merge_coplanar_triangles_to_quads(hull, points,
                                                  float(options['--angle']),
                                                  adjust_vertices=True)
        export_mesh_to_obj(points, faces, out, group=options['--name'])
        if animate:
            visualize_mesh(points, faces, radius=1.0)
    else:
        # Export original triangulated hull
        export_to_obj(points, hull, out)
        if animate:
            visualize_points_on_sphere(points, radius=1.0, hull=hull)


def dual_of_triangulation(points, min_edge=MIN_EDGE_FRACTION):
    """The polar dual of the points' convex hull: one face per point, no triangles.

    The hull of points on a sphere is a triangulation, and its dual turns every
    triangle into a three-valent vertex and every point into a face with as many
    sides as that point had neighbours. So the face census IS the triangulation's
    degree distribution: evenly spread points give 12 pentagons and the rest
    hexagons (Euler's formula forces exactly 12 when no degree strays from 5 or
    6), while clumpier points give anything from triangles to octagons. That's
    what --relax steers.

    Polar reciprocation, not centroids-joined-up, so the faces are exactly flat
    rather than slightly saddle-shaped -- see polar_dual in genGoldberg.py.

    @param min_edge: shortest edge to allow, as a fraction of the median; 0 to
        leave the poles exactly where they fall (see separate_short_edges)
    @returns (vertices, faces), scaled to a circumradius of 1
    """
    (vertices, faces) = polar_dual(np.asarray(points, dtype=float))
    if min_edge > 0:
        vertices = separate_short_edges(vertices, faces, min_edge)
    longest = np.abs(np.linalg.norm(vertices, axis=1)).max()
    return (vertices / longest, faces)


def edges_of(faces):
    """Every edge of a face list, as (lower index, higher index) pairs."""
    return {tuple(sorted((face[i], face[(i + 1) % len(face)])))
            for face in faces for i in range(len(face))}


def flatten_faces(vertices, faces, strength=1.0):
    """Nudge each face's corners towards that face's own best-fit plane.

    A vertex belongs to three faces pulling it three ways, so the corrections are
    averaged rather than applied one after another. Called after moving vertices
    around, to win back the flatness that the move cost.
    """
    corrections = np.zeros_like(vertices)
    counts = np.zeros(len(vertices))
    for face in faces:
        corner = vertices[face]
        centre = corner.mean(axis=0)
        # The least-spread direction is the fitted plane's normal.
        (*_, singular) = np.linalg.svd(corner - centre)
        normal = singular[-1]
        for (i, v) in enumerate(face):
            offset = np.dot(corner[i] - centre, normal)
            corrections[v] -= strength * offset * normal
            counts[v] += 1
    counts[counts == 0] = 1
    return vertices + corrections / counts[:, None]


def separate_short_edges(vertices, faces, min_fraction=MIN_EDGE_FRACTION,
                         rounds=200):
    """Push apart vertices that landed almost on top of one another.

    The dual of a triangulation puts a vertex at each triangle's pole, and two
    nearly coplanar triangles give two poles a hair apart -- an edge the player
    can't see, between two vertices they can't tell apart. This walks the short
    edges apart to min_fraction of the median edge length, re-flattening the
    faces after each nudge so they don't bow in the process.

    Both steps are small and local, so the solid stays convex and roughly
    spherical; what it stops being is EXACTLY flat-faced, and the residual bow is
    reported by the caller. (An alternative would be to merge the offending pair
    of triangles before dualizing, which keeps flatness exact but costs a face.)

    @returns the adjusted vertices
    """
    vertices = np.array(vertices, dtype=float)
    edges = sorted(edges_of(faces))
    if not edges:
        return vertices

    def lengths(points):
        return np.array([np.linalg.norm(points[a] - points[b]) for (a, b) in edges])

    target = min_fraction * float(np.median(lengths(vertices)))
    print(f'Separating vertices closer than {target:.3f} '
          f'({min_fraction:.0%} of the median edge)')

    for round_number in range(rounds):
        current = lengths(vertices)
        short = [i for (i, length) in enumerate(current) if length < target]
        if not short:
            break
        for i in short:
            (a, b) = edges[i]
            gap = vertices[b] - vertices[a]
            distance = np.linalg.norm(gap)
            if distance < 1e-12:
                # Exactly coincident: any direction will do to get them apart.
                gap = np.random.normal(size=3)
                distance = np.linalg.norm(gap)
            # Half the shortfall each, damped so neighbouring short edges don't
            # fight each other into an overshoot.
            push = 0.25 * (target - distance) * gap / distance
            vertices[a] -= push
            vertices[b] += push
        vertices = flatten_faces(vertices, faces)

    final = lengths(vertices)
    print(f'  shortest edge {final.min():.3f} after {round_number + 1} rounds '
          f'(target {target:.3f})')
    return vertices


def choose_seed_sizes(n):
    """Sizes for the seed polygons of the --seeds method, totalling n vertices.

    Each is 3 plus three coin flips, so 4s and 5s are common and 3s and 6s are
    the tails (1:3:3:1). The last seed is trimmed or dropped to hit n exactly,
    since the total has to match the vertex count asked for.
    """
    sizes = []
    while sum(sizes) < n:
        sizes.append(3 + sum(random.randint(0, 1) for _ in range(3)))
    excess = sum(sizes) - n
    if excess:
        # Trimming the last one keeps it a polygon if it can afford the loss,
        # and otherwise it goes and the shortfall lands on another seed.
        last = sizes.pop()
        if last - excess >= 3:
            sizes.append(last - excess)
        else:
            shortfall = n - sum(sizes)
            if shortfall >= 3:
                sizes.append(shortfall)
            elif shortfall:
                sizes[-1] += shortfall
    return sizes


def seed_polygon(centre, size, angular_radius, phase):
    """One seed: `size` points on a small circle about `centre`, on the sphere.

    Points on a circle are coplanar, and evenly spaced ones make a regular
    polygon -- so the seed is exactly flat and regular before the hull ever sees
    it, with no relaxation needed to keep it that way.
    """
    # Any two directions across the centre will do as the circle's frame.
    across = np.cross(centre, [0.0, 0.0, 1.0])
    if np.linalg.norm(across) < 1e-6:
        across = np.cross(centre, [0.0, 1.0, 0.0])
    u = across / np.linalg.norm(across)
    v = np.cross(centre, u)

    points = []
    for i in range(size):
        angle = phase + 2 * np.pi * i / size
        offset = np.cos(angle) * u + np.sin(angle) * v
        points.append(np.cos(angular_radius) * np.array(centre)
                      + np.sin(angular_radius) * offset)
    return points


def seeded_solid(n, relax=DEFAULT_RELAX, animate=True):
    """Scatter seed polygons over a sphere and let the hull fill the gaps.

    The seeds are placed as small regular polygons on the sphere, each within its
    own cap, so every other vertex lies below its plane and the hull keeps it as
    a single face. The gaps between seeds come out as triangles, which is what
    keeps them flat -- no planarization step anywhere.

    Worth knowing what this can and can't give you: with S seeds on n vertices,
    Euler's formula fixes the number of filler triangles at T = n + 2S - 4, no
    matter how the seeds are packed. Seeds averaging 4.5 sides means S = n/4.5
    and so about 15% of the faces are seeds. Tighter packing only makes the
    triangles smaller. --dual is the method to reach for if you want the census
    dominated by larger faces.

    @returns (vertices, faces)
    """
    sizes = choose_seed_sizes(n)
    print(f"Seeds: {len(sizes)} polygons of sizes {sorted(sizes)} "
          f"totalling {sum(sizes)} vertices")
    centres = relaxed_points(len(sizes), relax, animate)

    # How big each seed can be: most of the way to its nearest neighbour, halved
    # because that neighbour is coming the other way. Per seed rather than one
    # global radius, so a seed with room to spare uses it and leaves fewer
    # filler triangles.
    cosines = np.clip(centres @ centres.T, -1.0, 1.0)
    np.fill_diagonal(cosines, -1.0)         # ignore each seed's distance to itself
    nearest = np.arccos(cosines).min(axis=1)

    vertices = []
    for (centre, size, gap) in zip(centres, sizes, nearest):
        vertices += seed_polygon(centre, size, SEED_FILL * gap / 2,
                                 phase=random.uniform(0, 2 * np.pi))
    vertices = np.array(vertices)

    hull = ConvexHull(vertices)
    faces = merge_coplanar_faces(vertices, hull)
    kept = sorted(len(f) for f in faces if len(f) > 3)
    if kept != sorted(s for s in sizes if s > 3):
        print(f"Warning: the hull kept {kept} as faces, but the seeds were "
              f"{sorted(s for s in sizes if s > 3)} -- a seed's plane may have "
              f"caught another vertex.", file=sys.stderr)
    return (vertices, faces)


def relaxed_points(n: int, relax: float = DEFAULT_RELAX, animate: bool = True):
    """n points on the unit sphere, spread out by the given fraction.

    relax=0 leaves them where they fell: clumps, gaps, and a wide spread of
    vertex degrees. relax=1 spreads them until the repulsion converges, which
    drives nearly every degree to 5 or 6. In between, the points are moved that
    fraction of the way to their settled positions and put back on the sphere.

    Interpolating rather than stopping the simulation early, because a fixed
    iteration count means something different at every n, while "halfway to
    settled" means the same thing at any size.
    """
    raw = generate_random_points_on_sphere(n, radius=1.0)
    print(f"Generated {n} points on unit sphere")
    if relax <= 0:
        print("Leaving them unrelaxed (--relax 0)")
        return raw

    settled = random_with_repulsion(raw.copy(), animate=animate)
    if relax >= 1:
        return settled

    blended = (1 - relax) * raw + relax * settled
    blended /= np.linalg.norm(blended, axis=1)[:, None]
    print(f"Moved them {relax:.0%} of the way to evenly spread")
    return blended


def random_with_repulsion(points, animate: bool = True):
    """Spread the given points over the sphere until the repulsion converges."""
    # print("Initial points:")
    # print(points)

    # Apply repulsion simulation to spread points evenly
    # Parameters scale with number of points for better convergence
    print("\nSimulating repulsion with real-time animation...")
    adjusted_points = simulate_repulsion(
        points,
        radius=1.0,
        max_iterations=1000,
        force_strength=0.025,  # Lower for more points
        max_force=0.25,        # Lower cap for stability
        damping=0.75,          # Higher damping for faster convergence
        max_velocity=0.05,     # Allow some movement but cap it
        convergence_threshold=0.001,  # Max movement threshold (per particle)
        animate=animate,
        update_interval=5    # Update display every n iterations
    )

    # print("\nAdjusted points:")
    # print(adjusted_points)
    return adjusted_points


def export_to_obj(points, hull, filename='polyhedron.obj'):
    """
    Export a convex hull to Wavefront OBJ format.

    Args:
        points: numpy array of shape (n, 3) with vertex coordinates
        hull: ConvexHull object from scipy.spatial
        filename: output filename (default: 'polyhedron.obj')
    """
    with open(filename, 'w') as f:
        f.write("group polyhedron\n")
        f.write("#vertices\n")

        # Write all vertices
        for point in points:
            f.write(f"v {point[0]} {point[1]} {point[2]}\n")

        f.write("#face defs\n")

        # Write all faces (triangles from convex hull)
        # Note: OBJ format uses 1-based indexing, so add 1 to each index
        for simplex in hull.simplices:
            # Each simplex is a triangle with 3 vertex indices.
            # Orient consistently outward -- hull.simplices alone are not
            # consistently wound (see orient_face_outward).
            (a, b, c) = orient_face_outward(simplex, points)
            f.write(f"f {a + 1} {b + 1} {c + 1}\n")

    print(f"Exported convex hull to {filename}")
    print(f"  Vertices: {len(points)}")
    print(f"  Faces: {len(hull.simplices)}")

if __name__ == "__main__":
    main()