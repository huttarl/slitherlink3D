import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D


def main():
    # Set random seed for reproducibility (optional)
    np.random.seed(42)

    # Generate 20 random points on unit sphere
    n = 20
    points = generate_random_points_on_sphere(n, radius=1.0)

    print(f"Generated {n} points on unit sphere:")
    print(points)

    # Visualize the points
    visualize_points_on_sphere(points, radius=1.0)


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


if __name__ == "__main__":
    main()
