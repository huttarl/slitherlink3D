"""Generate random polyhedra, for use in Slitherlink3D puzzles.
I used Claude to draft the code.
We'll start with random points on a sphere, then spread them out evenly using repulsion.

The plan is then to convert to a polyhedron, either by computing the convex hull,
or Delaunay triangulation, or something similar.

We'll likely end up with only triangular faces, because the odds of 4 nearby points
being coplanar are so low. But we may convert near-coplanar squares to actual squares
if possible.
"""

import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
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
                            c='red', marker='o', s=100, alpha=0.8)

        # Set labels and limits
        ax.set_xlabel('X')
        ax.set_ylabel('Y')
        ax.set_zlabel('Z')
        max_range = radius * 1.1
        ax.set_xlim([-max_range, max_range])
        ax.set_ylim([-max_range, max_range])
        ax.set_zlim([-max_range, max_range])

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
        total_movement = np.sum(np.linalg.norm(velocities, axis=1))

        if iteration % 100 == 0:
            print(f"Iteration {iteration}: total movement = {total_movement:.6f}")

        # Update display if animating
        if animate and iteration % update_interval == 0:
            scatter._offsets3d = (points[:, 0], points[:, 1], points[:, 2])
            title.set_text(f'Repulsion Simulation - Iteration {iteration}')
            fig.canvas.draw()
            fig.canvas.flush_events()

        if total_movement < convergence_threshold:
            print(f"Converged after {iteration} iterations (movement = {total_movement:.6f})")
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
               c='red', marker='o', s=100, alpha=0.8, label='Random vertices')

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

    ax.legend()

    plt.show()

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
    n = 70

    points = random_with_repulsion(n) if method == 'random_repulsion' else generate_golden_spiral(n)

    # Compute convex hull
    print("\nComputing convex hull...")
    hull = ConvexHull(points)

    print(f"Convex hull has {len(hull.vertices)} vertices and {len(hull.simplices)} faces")
    print(f"All vertices are on hull: {len(hull.vertices) == n}")

    # Visualize the adjusted points with convex hull
    visualize_points_on_sphere(points, radius=1.0, hull=hull)


def random_with_repulsion(n: int):
    # Set random seed for reproducibility (optional)
    np.random.seed()

    # Generate random points on unit sphere
    points = generate_random_points_on_sphere(n, radius=1.0)

    print(f"Generated {n} points on unit sphere")
    print("Initial points:")
    print(points)

    # Apply repulsion simulation to spread points evenly
    print("\nSimulating repulsion with real-time animation...")
    adjusted_points = simulate_repulsion(
        points,
        radius=1.0,
        max_iterations=2000,
        force_strength=0.05,  # Reduced from 0.1
        max_force=0.5,  # Reduced from 1.0
        damping=0.85,  # Reduced from 0.9 for more damping
        max_velocity=0.05,  # Reduced from 0.1
        convergence_threshold=1e-3,
        animate=True,
        update_interval=10  # Update display every 10 iterations
    )

    print("\nAdjusted points:")
    print(adjusted_points)
    return adjusted_points


if __name__ == "__main__":
    main()