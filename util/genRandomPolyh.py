import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D


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
                       convergence_threshold=1e-4):
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

    Returns:
        Adjusted points on sphere surface
    """
    points = points.copy()
    n = len(points)
    velocities = np.zeros_like(points)

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

        if total_movement < convergence_threshold:
            print(f"Converged after {iteration} iterations (movement = {total_movement:.6f})")
            break
    else:
        print(f"Reached max iterations ({max_iterations})")

    return points


def visualize_points_on_sphere(points, radius=1.0):
    """
    Visualize points on a sphere using matplotlib.

    Args:
        points: numpy array of shape (n, 3) with point coordinates
        radius: radius of the sphere for reference wireframe
    """
    fig = plt.figure(figsize=(10, 10))
    ax = fig.add_subplot(111, projection='3d')

    # Plot the points
    ax.scatter(points[:, 0], points[:, 1], points[:, 2],
               c='red', marker='o', s=100, alpha=0.8, label='Random vertices')

    # Draw a wireframe sphere for reference
    u = np.linspace(0, 2 * np.pi, 30)
    v = np.linspace(0, np.pi, 20)
    x = radius * np.outer(np.cos(u), np.sin(v))
    y = radius * np.outer(np.sin(u), np.sin(v))
    z = radius * np.outer(np.ones(np.size(u)), np.cos(v))

    ax.plot_wireframe(x, y, z, color='lightblue', alpha=0.3, linewidth=0.5)

    # Set labels and title
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')
    ax.set_title(f'{len(points)} Random Points on Unit Sphere')

    # Set equal aspect ratio
    max_range = radius * 1.1
    ax.set_xlim([-max_range, max_range])
    ax.set_ylim([-max_range, max_range])
    ax.set_zlim([-max_range, max_range])

    ax.legend()

    plt.show()


def main():
    # Set random seed for reproducibility (optional)
    np.random.seed(42)

    # Generate 20 random points on unit sphere
    n = 20
    points = generate_random_points_on_sphere(n, radius=1.0)

    print(f"Generated {n} points on unit sphere")
    print("Initial points:")
    print(points)

    # Apply repulsion simulation to spread points evenly
    print("\nSimulating repulsion...")
    adjusted_points = simulate_repulsion(
        points,
        radius=1.0,
        max_iterations=1000,
        force_strength=0.1,
        max_force=1.0,
        damping=0.9,
        max_velocity=0.1,
        convergence_threshold=1e-4
    )

    print("\nAdjusted points:")
    print(adjusted_points)

    # Visualize the adjusted points
    visualize_points_on_sphere(adjusted_points, radius=1.0)


if __name__ == "__main__":
    main()