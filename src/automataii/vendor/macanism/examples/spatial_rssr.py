import numpy as np
import matplotlib.pyplot as plt
from mechanism import get_joints, Vector, Mechanism

# Define Joints
O1, A, B, O2 = get_joints("O1 A B O2")

# Define mechanism geometry and parameters
L_O1A = 1.0  # Length of input crank O1A
L_AB = 2.5  # Length of coupler AB
L_O2B = 1.5  # Length of output link O2B

# Position of fixed joints
O1.x, O1.y, O1.z = 0.0, 0.0, 0.0
O2_pos_x, O2_pos_y, O2_pos_z = 2.0, 1.0, 0.5
O2.x, O2.y, O2.z = O2_pos_x, O2_pos_y, O2_pos_z

# Define Vectors
# Input crank: O1A, rotates around Z-axis of O1 (global Z-axis since O1 is at origin)
# Its 'get' method will be _tangent (takes theta, assumes phi=pi/2 for rotation in XY plane)
vec_O1A = Vector((O1, A), r=L_O1A, phi=np.pi / 2)

# Coupler: AB, fixed length, general spatial orientation
# Its 'get' method should be _tangent_spherical (takes theta_AB, phi_AB)
vec_AB = Vector((A, B), r=L_AB)

# Output link: O2B, rotates around Z-axis of O2 (local Z-axis parallel to global Z)
# Its 'get' method will be _tangent (takes theta, assumes phi=pi/2 for rotation in its local XY plane)
vec_O2B = Vector((O2, B), r=L_O2B, phi=np.pi / 2)  # This vector is from O2 to B

# Ground link: O1O2 (fixed)
vec_O1O2 = Vector((O1, O2), x=O2_pos_x, y=O2_pos_y, z=O2_pos_z, style="ground")

# Define the mapping for unknowns: [theta_AB, phi_AB, theta_O2B]
unknown_map = [
    (vec_AB, "theta"),  # Unknown 0: theta angle of coupler AB
    (vec_AB, "phi"),  # Unknown 1: phi angle of coupler AB
    (vec_O2B, "theta"),  # Unknown 2: theta angle of output link O2B
]

# Loop closure equation: vec_O1A + vec_AB - vec_O2B - vec_O1O2 = 0
# Unknowns for fsolve: x = [theta_AB, phi_AB, theta_O2B]
#   - theta_AB: Azimuthal angle of coupler AB
#   - phi_AB: Polar (inclination) angle of coupler AB
#   - theta_O2B: Angle of output link O2B around its local Z-axis


def loops(x_unknowns, driven_input_theta_O1A):
    """
    Loop closure equations for the RSSR mechanism.

    Args:
        x_unknowns (list/array): Unknown variables [theta_AB, phi_AB, theta_O2B].
        driven_input_theta_O1A (float): Driven angle for the input crank O1A.

    Returns:
        np.ndarray: Array of 3 residuals (x, y, z components of the loop equation).
    """
    theta_AB, phi_AB, theta_O2B = x_unknowns

    # Calculate components of each vector based on current inputs/unknowns
    # Call the vector objects directly. This invokes their __call__ method, which in turn
    # calls the .get() method of their respective .pos object.
    # This updates the internal state (x,y,z components) of each vector's Position object
    # and also updates the global position of their head joints.
    vec_O1A(driven_input_theta_O1A)
    vec_AB(theta_AB, phi_AB)
    vec_O2B(theta_O2B)
    vec_O1O2()  # For fixed vectors, call to set their state from their fixed definition.

    # Vector loop equation: O1A + AB - O2B - O1O2 = 0
    # The .pos.x, .pos.y, .pos.z attributes now hold the calculated components of each vector.
    loop_residual_x = vec_O1A.pos.x + vec_AB.pos.x - vec_O2B.pos.x - vec_O1O2.pos.x
    loop_residual_y = vec_O1A.pos.y + vec_AB.pos.y - vec_O2B.pos.y - vec_O1O2.pos.y
    loop_residual_z = vec_O1A.pos.z + vec_AB.pos.z - vec_O2B.pos.z - vec_O1O2.pos.z

    return np.array([loop_residual_x, loop_residual_y, loop_residual_z])


# Velocity loop equations
def loops_vel(
    x_dot_unknowns,
    driven_input_vel,
    x_pos_unknowns,
    driven_input_pos,
    vectors_list,
    analysis_type_str,
):
    """
    Calculates the velocity loop closure residuals.
    Loop: d/dt (O1A + AB - O2B - O1O2) = 0 -> vel_O1A + vel_AB - vel_O2B = 0

    Args:
        x_dot_unknowns (list/array): Unknown angular velocities [theta_AB_dot, phi_AB_dot, theta_O2B_dot].
        driven_input_vel (float): Driven angular velocity for input crank O1A (theta1_dot).
        x_pos_unknowns (list/array): Solved position unknowns [theta_AB, phi_AB, theta_O2B] from pos analysis.
        driven_input_pos (float): Solved position for input crank O1A (theta1).
        vectors_list (list): The list of Vector objects in the mechanism.
        analysis_type_str (str): Should be 'vel'.

    Returns:
        np.ndarray: Array of 3 velocity residuals (x, y, z components).
    """
    theta_AB_dot, phi_AB_dot, theta_O2B_dot = x_dot_unknowns
    theta_AB_pos, phi_AB_pos, theta_O2B_pos = x_pos_unknowns
    vec_O1A, vec_AB, vec_O2B, vec_O1O2 = vectors_list

    # --- Context Update Needed ---
    # Before calculating velocities, the internal positional context (pos_r, pos_theta, pos_phi)
    # within each vector's .vel object must be updated based on the solved positions
    # (x_pos_unknowns, driven_input_pos).
    # This might involve setting vec.pos attributes and then calling vec._update_velocity().
    # Example (conceptual):
    # vec_O1A.pos.theta = driven_input_pos # Already done by Mechanism?
    # vec_AB.pos.theta = theta_AB_pos
    # vec_AB.pos.phi = phi_AB_pos
    # vec_O2B.pos.theta = theta_O2B_pos
    # for vec in vectors_list: vec._update_velocity()
    # This update step needs to be handled correctly by the Mechanism class before this function is called.
    # Assuming context is correctly set for now.
    # --- End Context Update ---

    # Calculate velocity components by calling the .vel() method of each vector
    # This uses the .vel.get method (e.g., _tangent, _tangent_spherical)
    # which requires the positional context (pos_r, theta, phi) to be set correctly inside the .vel object.
    vec_O1A(driven_input_vel)
    vec_AB(theta_AB_dot, phi_AB_dot)
    vec_O2B(theta_O2B_dot)
    vec_O1O2()  # Fixed vector, velocity is zero

    # Calculate residuals using the .vel.x, .vel.y, .vel.z components
    residual_vx = vec_O1A.vel.x + vec_AB.vel.x - vec_O2B.vel.x - vec_O1O2.vel.x
    residual_vy = vec_O1A.vel.y + vec_AB.vel.y - vec_O2B.vel.y - vec_O1O2.vel.y
    residual_vz = vec_O1A.vel.z + vec_AB.vel.z - vec_O2B.vel.z - vec_O1O2.vel.z

    return np.array([residual_vx, residual_vy, residual_vz])


# Acceleration loop equations
def loops_acc(
    x_ddot_unknowns,
    driven_input_acc,
    x_dot_unknowns,
    driven_input_vel,
    x_pos_unknowns,
    driven_input_pos,
    vectors_list,
    analysis_type_str,
):
    """
    Calculates the acceleration loop closure residuals.
    Loop: d/dt (vel_O1A + vel_AB - vel_O2B) = 0 -> acc_O1A + acc_AB - acc_O2B = 0

    Args:
        x_ddot_unknowns (list/array): Unknown angular accelerations [theta_AB_ddot, phi_AB_ddot, theta_O2B_ddot].
        driven_input_acc (float): Driven angular acceleration for input crank O1A (theta1_ddot).
        x_dot_unknowns (list/array): Solved angular velocities [theta_AB_dot, phi_AB_dot, theta_O2B_dot].
        driven_input_vel (float): Solved angular velocity for input crank O1A (theta1_dot).
        x_pos_unknowns (list/array): Solved position unknowns [theta_AB, phi_AB, theta_O2B].
        driven_input_pos (float): Solved position for input crank O1A (theta1).
        vectors_list (list): The list of Vector objects in the mechanism.
        analysis_type_str (str): Should be 'acc'.

    Returns:
        np.ndarray: Array of 3 acceleration residuals (x, y, z components).
    """
    theta_AB_ddot, phi_AB_ddot, theta_O2B_ddot = x_ddot_unknowns
    theta_AB_dot, phi_AB_dot, theta_O2B_dot = x_dot_unknowns  # Solved velocities
    theta_AB_pos, phi_AB_pos, theta_O2B_pos = x_pos_unknowns  # Solved positions
    vec_O1A, vec_AB, vec_O2B, vec_O1O2 = vectors_list

    # --- Context Update Needed ---
    # Before calculating accelerations, the internal positional and velocity context
    # (pos_r...phi, vel_r_dot...phi_dot) within each vector's .acc object must be updated
    # based on the solved positions and velocities.
    # This might involve setting vec.pos and vec.vel attributes and then calling vec._update_acceleration().
    # Example (conceptual):
    # Update positions first (as in loops_vel conceptual example)
    # Then update velocities based on x_dot_unknowns, driven_input_vel
    # vec_O1A.vel.omega = driven_input_vel
    # vec_AB.vel.omega = theta_AB_dot
    # vec_AB.vel.phi_dot = phi_AB_dot
    # vec_O2B.vel.omega = theta_O2B_dot
    # ... (handle r_dot components if any links change length)
    # Then call: for vec in vectors_list: vec._update_acceleration()
    # This update step needs to be handled correctly by the Mechanism class before this function is called.
    # Assuming context is correctly set for now.
    # --- End Context Update ---

    # Calculate acceleration components by calling the .acc() method of each vector
    # This uses the .acc.get method (e.g., _tangent, _tangent_spherical)
    # which requires positional and velocity context to be set correctly inside the .acc object.
    vec_O1A(driven_input_acc)
    vec_AB(theta_AB_ddot, phi_AB_ddot)
    vec_O2B(theta_O2B_ddot)
    vec_O1O2()  # Fixed vector, acceleration is zero

    # Calculate residuals using the .acc.x, .acc.y, .acc.z components
    residual_ax = vec_O1A.acc.x + vec_AB.acc.x - vec_O2B.acc.x - vec_O1O2.acc.x
    residual_ay = vec_O1A.acc.y + vec_AB.acc.y - vec_O2B.acc.y - vec_O1O2.acc.y
    residual_az = vec_O1A.acc.z + vec_AB.acc.z - vec_O2B.acc.z - vec_O1O2.acc.z

    return np.array([residual_ax, residual_ay, residual_az])


# Initial guess for unknown angles [theta_AB, phi_AB, theta_O2B]
# These need to be reasonable for fsolve to converge.
# (Units are radians)
initial_guess_pos = np.deg2rad([45.0, 60.0, 30.0])
initial_guess_vel = np.array([0.1, 0.1, 0.1])  # Placeholder, adjust if needed
initial_guess_acc = np.array([0.0, 0.0, 0.0])  # Placeholder, adjust if needed

# Driven input: angle of O1A (e.g., one full rotation)
num_steps = 100
input_crank_angles = np.linspace(0, 2 * np.pi, num_steps)
input_angular_velocity = (2 * np.pi) / (
    num_steps * 0.01
)  # Assuming 0.01s per step for velocity calculation
input_velocities = np.full(num_steps, input_angular_velocity)
input_accelerations = np.zeros(num_steps)

# Create Mechanism
# For a true 3D mechanism, loops_vel and loops_acc might be needed if not easily derivable
# by differentiating the position loop equations symbolically or if they are complex.
# For now, we assume they can be derived by the library.
rssr_mechanism = Mechanism(
    vectors=[vec_O1A, vec_AB, vec_O2B, vec_O1O2],
    origin=O1,  # Origin for global coordinate system calculations if needed
    loops=loops,
    pos=input_crank_angles,  # Driven position array
    vel=input_velocities,  # Driven velocity array
    acc=input_accelerations,  # Driven acceleration array
    guess=(initial_guess_pos, initial_guess_vel, initial_guess_acc),
    loops_vel=loops_vel,  # Add placeholder
    loops_acc=loops_acc,  # Add placeholder
    unknown_map=unknown_map,  # Pass the mapping
    # We need to tell the mechanism which vector is the input vector.
    # The `pos`, `vel`, `acc` arrays correspond to the input for this vector.
    # This is implicitly the first vector in `loops` that takes the `inp` argument.
    # Let's ensure `Mechanism` class understands this or has a way to specify the input vector.
    # The current Mechanism takes the driven vector's value as the second arg to `loops`.
    # And it calls `vector(*input)` where `vector` is assumed to be the input vector object.
    # Here, `vec_O1A` is the input vector.
    # The mechanism will try to call `vec_O1A.pos(driven_input_theta_O1A_scalar_value)`
)

# Perform kinematic analysis
print("Starting kinematic analysis for RSSR mechanism...")
try:
    rssr_mechanism.iterate()
    print("Kinematic analysis complete.")

    # Plotting and Animation (Commented out for testing)
    # print("Generating plot...")
    # fig, ax = rssr_mechanism.plot(cushion=1.0, show_joints=True)
    # ax.set_title("Spatial RSSR Mechanism - Static Plot")
    # plt.show()
    #
    # print("Generating animation...")
    # ani, fig_ani, ax_ani = rssr_mechanism.get_animation(cushion=1.0, show_joints=True, velocity=True, acceleration=True)
    # # To save the animation:
    # # print("Saving animation...")
    # # ani.save('spatial_rssr_mechanism.mp4', writer='ffmpeg', fps=30)
    # # print("Animation saved to spatial_rssr_mechanism.mp4")
    # ax_ani.set_title("Spatial RSSR Mechanism - Animation")
    # plt.show()

except Exception as e:
    print(f"An error occurred during RSSR mechanism analysis: {e}")
    import traceback

    traceback.print_exc()

print("RSSR Example Finished.")
