"""Generate random polyhedra, for use in Slitherlink3D puzzles.
I used Claude to draft the code.

Choose the method in main():
method = 'random_repulsion': Start with random points on a sphere, then spread them out evenly by simulating repulsion.
method = 'golden_spiral': Use golden spiral to lay out points evenly (yields more quads around equator).

We then to convert to a polyhedron by computing the convex hull, then merge almost-coplanar
adjacent triangles into quads. The resulting mesh is exported to OBJ format.
"""

import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial import ConvexHull


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


def export_mesh_to_obj(points, faces, filename='polyhedron.obj'):
    """
    Export a mesh with mixed triangle and quad faces to Wavefront OBJ format.
    
    Args:
        points: numpy array of shape (n, 3) with vertex coordinates
        faces: list of faces, where each face is a list of vertex indices
        filename: output filename (default: 'polyhedron.obj')
    """
    with open(filename, 'w') as f:
        f.write("# Polyhedron with triangles and quads\n")
        f.write("g polyhedron\n")
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


def main():
    method = 'random_repulsion'
    # method = 'golden_spiral'
    n = 70  # Number of vertices
    merge_quads = True  # Set to True to merge coplanar triangles into quads
    angle_threshold = 5.0  # Degrees - lower values = stricter coplanarity requirement
    adjust_vertices = True  # If True, project quad vertices onto best-fit plane for exact coplanarity

    points = random_with_repulsion(n) if method == 'random_repulsion' else generate_golden_spiral(n)

    # Compute convex hull
    print("\nComputing convex hull...")
    hull = ConvexHull(points)

    print(f"Convex hull has {len(hull.vertices)} vertices and {len(hull.simplices)} faces")
    print(f"All vertices are on hull: {len(hull.vertices) == n}")

    if merge_quads:
        # Merge coplanar triangles into quads
        faces = merge_coplanar_triangles_to_quads(hull, points, angle_threshold, adjust_vertices)
        export_mesh_to_obj(points, faces, 'polyhedron_with_quads.obj')
        visualize_mesh(points, faces, radius=1.0)
    else:
        # Export original triangulated hull
        export_to_obj(points, hull, 'polyhedron_triangulated.obj')
        visualize_points_on_sphere(points, radius=1.0, hull=hull)


def random_with_repulsion(n: int):
    # Set random seed for reproducibility (optional)
    np.random.seed()

    # Generate random points on unit sphere
    points = generate_random_points_on_sphere(n, radius=1.0)

    print(f"Generated {n} points on unit sphere")
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
        animate=True,
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