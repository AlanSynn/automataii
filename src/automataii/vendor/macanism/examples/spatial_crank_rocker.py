"""Example of setting up a spatial (3D) mechanism.

Placeholder - Requires correct 3D loop functions.
"""

from mechanism import *
import numpy as np
import matplotlib.pyplot as plt

# Assuming mechanism classes are importable
# Need to adjust path based on execution context
try:
    from mechanism.mechanism import Mechanism, Joint, Vector, Position
    from mechanism.plotting import setup_plot_window, plot_vectors, plot_joints
    from mechanism.animation import Player  # Assuming Player is in animation
except ImportError:
    import sys
    import os

    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from mechanism.mechanism import Mechanism, Joint, Vector, Position
    from mechanism.plotting import setup_plot_window, plot_vectors, plot_joints
    from mechanism.animation import Player


def spatial_crank_rocker_example():
    """
    Defines and solves a simple spatial crank-rocker like mechanism.
    Input crank v1 rotates in the XY plane (about Z-axis at origin).
    Output link v_out rotates about a Z-axis fixed at (px, py, pz).
    Coupler v_coupler connects them.
    Loop: origin -> j1 (tip of v1) -> j_out_tip (tip of v_out) -> j_ground_pivot (base of v_out) -> origin
    This definition is slightly different, let's use:
    v1.pos (vector from j0 to j1)
    v_coupler.pos (vector from j1 to j_out_tip)
    v_out.pos (vector from j_ground_pivot to j_out_tip)
    v_ground_offset.pos (vector from j0 to j_ground_pivot) - this is fixed.

    Loop equation: v1.pos + v_coupler.pos = v_ground_offset.pos + v_out.pos
    This gives 3 scalar equations.
    Unknowns for fsolve (guess):
    1. v_coupler.pos.theta (inclination of coupler)
    2. v_coupler.pos.phi   (azimuth of coupler)
    3. v_out.pos.phi       (azimuth of output link, its theta is fixed to pi/2 for planar rotation)
    """

    # Define Link Lengths
    L1 = 1.0  # Input crank
    L2 = 2.5  # Coupler
    L3 = 1.5  # Output link

    # Define Output Pivot Location (base of v_out, relative to origin)
    px, py, pz = 2.0, 0.5, 0.5

    # --- Define Joints ---
    j0 = Joint("0", x=0, y=0, z=0, type="fixed")
    j1 = Joint("1")  # Tip of input crank v1
    j_ground_pivot = Joint(
        "gp", x=px, y=py, z=pz, type="fixed"
    )  # Base of output link v_out
    j_out_tip = Joint("ot")  # Tip of output link v_out

    # --- Define Vectors (Links) ---
    # Input crank: rotates in XY plane (theta=pi/2 fixed), phi is the input angle
    v1 = Vector(
        joints=(j0, j1), r=L1, theta=np.pi / 2, show=True, style="stroke", color="blue"
    )
    # Coupler: length L2, orientation (theta, phi) are unknowns
    v_coupler = Vector(
        joints=(j1, j_out_tip), r=L2, show=True, style="stroke", color="green"
    )
    # Output link: rotates in a plane parallel to XY at height pz (theta=pi/2 fixed), phi is an unknown
    v_out = Vector(
        joints=(j_ground_pivot, j_out_tip),
        r=L3,
        theta=np.pi / 2,
        show=True,
        style="stroke",
        color="red",
    )

    # Fixed ground offset vector (from origin to base of output link)
    # We don't strictly need this as a vector in the mechanism loops,
    # but it helps define j_ground_pivot's location.
    # Its components are (px, py, pz)

    # List of vectors for the mechanism
    # The order can matter for how guesses are interpreted if not named.
    # Driven vector should usually be first.
    vectors = [v1, v_coupler, v_out]

    # Define the loop equations for the mechanism
    # Loop: v1 + v_coupler - v_out - v_ground_offset = 0
    # where v_ground_offset is vector from j0 to j_ground_pivot
    # Target: j0.pos + v1.pos + v_coupler.pos = j_ground_pivot.pos + v_out.pos
    # (j1.pos_x, j1.pos_y, j1.pos_z) + (v_coupler.pos.x, v_coupler.pos.y, v_coupler.pos.z) = \
    # (px, py, pz) + (v_out.pos.x, v_out.pos.y, v_out.pos.z)
    # The mechanism solver handles this internally by ensuring joint consistency.
    # For a single loop closure:
    # pos(j0) + v1.pos + v_coupler.pos - v_out.pos - pos(vector from j0 to j_ground_pivot) = 0
    # Since j0 is origin (0,0,0)
    # v1.pos + v_coupler.pos - v_out.pos - (px, py, pz)_vector = 0
    # where (px,py,pz)_vector is represented by j_ground_pivot.pos if j0 is the global origin.

    # The mechanism class will try to satisfy:
    # For each joint, sum of incoming vector coords = sum of outgoing vector coords
    # Or, for a loop of vectors like vA + vB + vC = 0, it means tail of vA to head of vC is zero vector.
    # Our defined joints and vectors imply loops.
    # Loop 1: j0 -> j1 -> j_out_tip -> j_ground_pivot -> j0 (implicitly, if ground is connected)
    # The current `Mechanism` class calculates positions sequentially based on driven vector,
    # then uses fsolve on loop equations that must return 0.

    def loops(inputs, v1_obj, v_coupler_obj, v_out_obj, p_ground_pivot_coords):
        """Calculates residuals for 3D position loop equations.
        inputs: [coupler_theta, coupler_phi, out_phi]
        v1_obj: Vector object for the input crank
        v_coupler_obj: Vector object for the coupler
        v_out_obj: Vector object for the output link
        p_ground_pivot_coords: numpy array [px, py, pz]
        """
        coupler_th, coupler_ph, out_ph = inputs

        # Get coordinates for the current input angle (v1_obj.pos.phi is set by Mechanism.calculate)
        # v1 has r, theta fixed. Its get method should be _phi_varies_get (1 arg)
        v1_coords = v1_obj.pos(v1_obj.pos.phi)

        # Get coordinates for the coupler based on guess
        # v_coupler has r fixed. Its get method should be _tangent_spherical (2 args)
        coupler_coords = v_coupler_obj.pos(coupler_th, coupler_ph)

        # Get coordinates for the output link based on guess
        # v_out has r, theta fixed. Its get method should be _phi_varies_get (1 arg)
        out_coords = v_out_obj.pos(out_ph)

        # Loop closure equation:
        # j0_pos + v1_coords + coupler_coords = j_ground_pivot_pos + out_coords
        # (0,0,0) + v1_coords + coupler_coords = p_ground_pivot_coords + out_coords
        # Error vector = v1_coords + coupler_coords - out_coords - p_ground_pivot_coords

        error_x = (
            v1_coords[0] + coupler_coords[0] - out_coords[0] - p_ground_pivot_coords[0]
        )
        error_y = (
            v1_coords[1] + coupler_coords[1] - out_coords[1] - p_ground_pivot_coords[1]
        )
        error_z = (
            v1_coords[2] + coupler_coords[2] - out_coords[2] - p_ground_pivot_coords[2]
        )

        return [error_x, error_y, error_z]

    # Initial guess for unknowns: [coupler_theta, coupler_phi, out_phi]
    # These need to be reasonable for the linkage to assemble.
    # If v1 is at phi=0 (along X axis), j1 is at (L1,0,0)
    # If output is roughly aligned, j_out_tip could be (px+L3, py, pz)
    # Coupler connects (L1,0,0) to (px+L3, py, pz)
    # Vector_c = (px+L3-L1, py, pz). Then find its spherical coords.
    dx = px + L3 - L1
    dy = py
    dz = pz
    guess_coupler_r = np.sqrt(dx**2 + dy**2 + dz**2)  # Should be close to L2
    # print(f"L2={L2}, Initial guess for coupler length based on geometry: {guess_coupler_r}")
    guess_coupler_phi = np.arctan2(dy, dx)
    guess_coupler_theta = (
        np.arccos(dz / guess_coupler_r) if guess_coupler_r > 1e-9 else np.pi / 2
    )  # Avoid division by zero
    guess_out_phi = 0.0

    initial_guess = [guess_coupler_theta, guess_coupler_phi, guess_out_phi]

    # Create the mechanism
    # The Mechanism class needs to be adapted to pass these specific vector objects to loops.
    # Or, the loops function needs to be an attribute of Mechanism, finding vectors by name/index.
    # For now, let's assume we can pass them.
    # The `loops` function needs access to `px,py,pz`. We can use a lambda or functools.partial.
    p_gp_coords = np.array([j_ground_pivot.x, j_ground_pivot.y, j_ground_pivot.z])

    loop_func_wrapper = lambda inputs: loops(inputs, v1, v_coupler, v_out, p_gp_coords)

    # IMPORTANT: The `get` methods of Position objects need to be correctly set up by VectorBase.__init__.
    # v1.pos.get should be _phi_varies_get (1 arg: phi) based on r, theta fixed, phi=None init.
    # v_coupler.pos.get should be _tangent_spherical (2 args: theta, phi) based on r fixed, theta=None, phi=None init.
    # v_out.pos.get should be _phi_varies_get (1 arg: phi) based on r, theta fixed, phi=None init.

    # Create Mechanism instance
    # The `driven_vector_idx` refers to the `vectors` list. v1 is at index 0.
    # `num_inputs` for driven vector: v1 is driven by 1 angle (phi).
    mechanism = Mechanism(
        vectors=vectors,
        loops=loop_func_wrapper,  # Pass the wrapped loop function
        origin=j0,
        guess=initial_guess,
        driven_vector_idx=0,
        num_driven_inputs=1,  # v1.pos.phi is the input
    )

    # Define input motion for v1.pos.phi
    # Let v1.pos.phi rotate from 0 to 2*pi
    num_steps = 100
    input_phis = np.linspace(0, 2 * np.pi, num_steps)

    # --- Solve the mechanism ---
    print("Solving Spatial Crank-Rocker...")
    try:
        mechanism.calculate(input_phis, (v1.pos, "phi"))  # Drive v1.pos.phi
        print("Done solving.")
        solved = True
    except Exception as e:
        print(f"\nError during mechanism calculation: {e}")
        print(
            "Mechanism calculation failed. Check loop functions, guesses, or mechanism definition."
        )
        solved = False

    if solved:
        # --- Plotting ---
        print("Plotting results...")
        try:
            bounds = mechanism.get_bounds(for_animation=True)
            if bounds is None:
                print("Warning: Could not determine bounds for plotting.")
                # Set some default bounds if needed
                bounds = [
                    [-L1 - L2, L1 + L2 + px],
                    [-L1 - L2, L1 + L2 + py],
                    [-L2, L2 + pz],
                ]

            fig, ax = setup_plot_window(bounds)

            # Initial plot
            plot_vectors(ax, mechanism.vectors, 0)  # Plot initial position
            plot_joints(ax, mechanism.joints, 0)
            plt.title("Spatial Crank-Rocker Initial Position")
            # plt.show() # Show initial static plot

            # --- Animation ---
            print("Preparing animation...")

            ani_player, fig_ani, ax_ani = mechanism.get_animation(
                lims=None,  # Use bounds from get_bounds
                show_vel=False,
                show_acc=False,
            )
            # To show animation, you might need fig_ani.show() or similar depending on backend
            # For saving, use ani_player.save(...)
            print(f"Animation ready. Frames: {ani_player.frames}")
            # ani_player.save('spatial_crank_rocker.mp4', writer='ffmpeg', fps=30)
            # print("Animation saved to spatial_crank_rocker.mp4")
            plt.show()  # This will show the animation with the player controls
        except Exception as e:
            print(f"Error during plotting/animation: {e}")

    print("\nExample Run Summary:")
    print(f"Input crank (v1) length L1: {L1}")
    print(f"Coupler (v_coupler) length L2: {L2}")
    print(f"Output link (v_out) length L3: {L3}")
    print(f"Output pivot base (j_ground_pivot) at: ({px}, {py}, {pz})")

    # Print some output data if solved
    # if solved:
    #     print("\nSample solved output angles for v_out.pos.phi:")
    #     print(v_out.pos.phis[::10]) # Print every 10th solved phi for the output link


if __name__ == "__main__":
    spatial_crank_rocker_example()
