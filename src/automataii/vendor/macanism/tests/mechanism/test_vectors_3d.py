import pytest
import numpy as np
from mechanism.vectors import Velocity

# Constants for precision
RTOL = 1e-5
ATOL = 1e-8

# Test cases for Velocity._both_spherical
# Each tuple: (name, pos_r, pos_theta, pos_phi, r_dot, theta_dot, phi_dot, expected_vx, expected_vy, expected_vz)
velocity_test_cases = [
    (
        "radial_xy_plane_pos_x_axis",
        1.0,
        0.0,
        np.pi / 2,  # pos: (1,0,0)
        1.0,
        0.0,
        0.0,  # vel: r_dot=1
        1.0,
        0.0,
        0.0,  # expected: (1,0,0)
    ),
    (
        "radial_xy_plane_pos_y_axis",
        1.0,
        np.pi / 2,
        np.pi / 2,  # pos: (0,1,0)
        1.0,
        0.0,
        0.0,  # vel: r_dot=1
        0.0,
        1.0,
        0.0,  # expected: (0,1,0)
    ),
    (
        "tangential_xy_plane_ccw_pos_x_axis",
        1.0,
        0.0,
        np.pi / 2,  # pos: (1,0,0)
        0.0,
        1.0,
        0.0,  # vel: theta_dot=1 (omega=1)
        0.0,
        1.0,
        0.0,  # expected: (0,1,0) (vx=-r*sin(theta)*omega, vy=r*cos(theta)*omega for phi=pi/2)
        # Corrected: vx = -r*omega*sin(theta_val), vy = r*omega*cos(theta_val) if theta_val is current angle
        # With theta_dot, x = r*s(phi)c(th) -> vx = r_dot*s(phi)c(th) - r*s(phi)s(th)th_dot + r*c(phi)c(th)phi_dot
        # phi=pi/2 -> sin(phi)=1, cos(phi)=0. vx = -r*sin(th)*th_dot. Here th=0, so vx=0.
        # y = r*s(phi)s(th) -> vy = r_dot*s(phi)s(th) + r*s(phi)c(th)th_dot + r*c(phi)s(th)phi_dot
        # phi=pi/2 -> sin(phi)=1, cos(phi)=0. vy = r*cos(th)*th_dot. Here th=0, so vy=r*th_dot = 1.0*1.0 = 1.0
    ),
    (
        "tangential_xy_plane_ccw_pos_y_axis",
        1.0,
        np.pi / 2,
        np.pi / 2,  # pos: (0,1,0)
        0.0,
        1.0,
        0.0,  # vel: theta_dot=1 (omega=1)
        -1.0,
        0.0,
        0.0,  # expected: (-1,0,0) (vx = -r*sin(pi/2)*1 = -1, vy = r*cos(pi/2)*1 = 0)
    ),
    (
        "radial_3d_general_case",
        2.0,
        np.pi / 4,
        np.pi / 4,  # pos: r=2, th=45deg, phi=45deg (x=1,y=1,z=sqrt(2))
        1.0,
        0.0,
        0.0,  # vel: r_dot=1
        # vx = 1*sin(pi/4)cos(pi/4) = 1*(1/sqrt(2))*(1/sqrt(2)) = 0.5
        # vy = 1*sin(pi/4)sin(pi/4) = 1*(1/sqrt(2))*(1/sqrt(2)) = 0.5
        # vz = 1*cos(pi/4) = 1*(1/sqrt(2)) = 1/sqrt(2)
        0.5,
        0.5,
        np.sqrt(2) / 2,
    ),
    (
        "polar_motion_phi_dot_only",
        2.0,
        np.pi / 3,
        np.pi / 6,  # pos: r=2, th=60deg (azimuth), phi=30deg (polar)
        # x=2*s(30)c(60) = 2*(1/2)*(1/2)=0.5
        # y=2*s(30)s(60) = 2*(1/2)*(sqrt(3)/2)=sqrt(3)/2
        # z=2*c(30) = 2*sqrt(3)/2 = sqrt(3)
        0.0,
        0.0,
        0.5,  # vel: phi_dot=0.5 (polar ang. vel)
        # vx = r * phi_dot * cos(phi) * cos(theta) = 2 * 0.5 * cos(pi/6) * cos(pi/3) = 1 * (sqrt(3)/2) * (1/2) = sqrt(3)/4
        # vy = r * phi_dot * cos(phi) * sin(theta) = 2 * 0.5 * cos(pi/6) * sin(pi/3) = 1 * (sqrt(3)/2) * (sqrt(3)/2) = 3/4
        # vz = -r * phi_dot * sin(phi)             = -2 * 0.5 * sin(pi/6)             = -1 * (1/2) = -0.5
        np.sqrt(3) / 4,
        0.75,
        -0.5,
    ),
    (
        "azimuthal_motion_theta_dot_only",
        2.0,
        np.pi / 3,
        np.pi / 6,  # pos: r=2, th=60deg, phi=30deg
        0.0,
        0.5,
        0.0,  # vel: theta_dot=0.5 (azimuthal ang. vel)
        # vx = -r * theta_dot * sin(phi) * sin(theta) = -2 * 0.5 * sin(pi/6) * sin(pi/3) = -1 * (1/2) * (sqrt(3)/2) = -sqrt(3)/4
        # vy =  r * theta_dot * sin(phi) * cos(theta) =  2 * 0.5 * sin(pi/6) * cos(pi/3) =  1 * (1/2) * (1/2) = 1/4
        # vz = 0
        -np.sqrt(3) / 4,
        0.25,
        0.0,
    ),
    ("zero_velocity_input", 1.0, 0.0, np.pi / 2, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
    (
        "combined_motion_3d",
        1.5,
        np.pi / 6,
        np.pi / 3,  # pos: r=1.5, th=30deg, phi=60deg
        # x = 1.5*s(60)c(30) = 1.5*(sqrt(3)/2)*(sqrt(3)/2) = 1.5*3/4 = 1.125
        # y = 1.5*s(60)s(30) = 1.5*(sqrt(3)/2)*(1/2) = 1.5*sqrt(3)/4 approx 0.6495
        # z = 1.5*c(60) = 1.5*(1/2) = 0.75
        0.5,
        0.2,
        0.3,  # r_dot=0.5, theta_dot=0.2, phi_dot=0.3
        # vx = (r_dot*s(phi)c(th) + r*phi_dot*c(phi)c(th) - r*th_dot*s(phi)s(th))
        #    = (0.5*s(60)c(30) + 1.5*0.3*c(60)c(30) - 1.5*0.2*s(60)s(30))
        #    = (0.5*(sqrt(3)/2)*(sqrt(3)/2) + 0.45*(1/2)*(sqrt(3)/2) - 0.3*(sqrt(3)/2)*(1/2))
        #    = (0.5*3/4 + 0.45*sqrt(3)/4 - 0.3*sqrt(3)/4)
        #    = (0.375 + 0.15*sqrt(3)/4) = (0.375 + 0.0375*sqrt(3)) approx 0.375 + 0.06495 = 0.43995
        0.375 + 0.0375 * np.sqrt(3),
        # vy = (r_dot*s(phi)s(th) + r*phi_dot*c(phi)s(th) + r*th_dot*s(phi)c(th))
        #    = (0.5*s(60)s(30) + 1.5*0.3*c(60)s(30) + 1.5*0.2*s(60)c(30))
        #    = (0.5*(sqrt(3)/2)*(1/2) + 0.45*(1/2)*(1/2) + 0.3*(sqrt(3)/2)*(sqrt(3)/2))
        #    = (0.5*sqrt(3)/4 + 0.45/4 + 0.3*3/4)
        #    = (0.125*sqrt(3) + 0.1125 + 0.225) = 0.125*sqrt(3) + 0.3375 approx 0.2165 + 0.3375 = 0.5540
        0.125 * np.sqrt(3) + 0.3375,
        # vz = (r_dot*c(phi) - r*phi_dot*s(phi))
        #    = (0.5*c(60) - 1.5*0.3*s(60))
        #    = (0.25 - 0.225*sqrt(3)) approx 0.25 - 0.3897 = -0.1397
        0.25 - 0.225 * np.sqrt(3),
    ),
]


@pytest.mark.parametrize(
    "name, pos_r, pos_theta, pos_phi, r_dot, theta_dot, phi_dot, expected_vx, expected_vy, expected_vz",
    velocity_test_cases,
)
def test_velocity_both_spherical(
    name,
    pos_r,
    pos_theta,
    pos_phi,
    r_dot,
    theta_dot,
    phi_dot,
    expected_vx,
    expected_vy,
    expected_vz,
):
    """
    Tests Velocity._both_spherical for various scenarios.
    Note: The Velocity object itself doesn't use r, theta, phi for its state,
    but _both_spherical calculates vx, vy, vz based on inputs and pos_r, pos_theta, pos_phi.
    """
    # Instantiate a dummy Velocity object. Its own r, theta, phi are not directly used by _both_spherical's math.
    # What matters are pos_r, pos_theta, pos_phi which are set before calling.
    vel_vector = Velocity(r=0, theta=0, phi=0)  # Dummy values for constructor

    # Set the positional context required by _both_spherical
    vel_vector.pos_r = pos_r
    vel_vector.pos_theta = pos_theta
    vel_vector.pos_phi = pos_phi

    # Call the method to be tested
    result_xyz = vel_vector._both_spherical(r_dot, theta_dot, phi_dot)

    assert isinstance(result_xyz, np.ndarray), "Result should be a numpy array"
    assert result_xyz.shape == (3,), "Result should be a 3-element array"

    # Check if calculated vx, vy, vz are close to expected values
    assert np.isclose(result_xyz[0], expected_vx, rtol=RTOL, atol=ATOL), (
        f"{name}: vx mismatch. Expected {expected_vx}, got {result_xyz[0]}"
    )
    assert np.isclose(result_xyz[1], expected_vy, rtol=RTOL, atol=ATOL), (
        f"{name}: vy mismatch. Expected {expected_vy}, got {result_xyz[1]}"
    )
    assert np.isclose(result_xyz[2], expected_vz, rtol=RTOL, atol=ATOL), (
        f"{name}: vz mismatch. Expected {expected_vz}, got {result_xyz[2]}"
    )

    # Also check if the internal x, y, z of the vector object are updated
    assert np.isclose(vel_vector.x, expected_vx, rtol=RTOL, atol=ATOL), (
        f"{name}: internal vel_vector.x mismatch"
    )
    assert np.isclose(vel_vector.y, expected_vy, rtol=RTOL, atol=ATOL), (
        f"{name}: internal vel_vector.y mismatch"
    )
    assert np.isclose(vel_vector.z, expected_vz, rtol=RTOL, atol=ATOL), (
        f"{name}: internal vel_vector.z mismatch"
    )


# Test cases for Acceleration._both_spherical
# Each tuple: (
#   name,
#   pos_r, pos_theta, pos_phi,       # Position context
#   vel_r_dot, vel_omega, vel_phi_dot, # Velocity context (omega is theta_dot)
#   r_ddot, alpha, phi_ddot_accel,    # Acceleration inputs (alpha is theta_ddot for acceleration)
#   expected_ax, expected_ay, expected_az
# )
# Note: In our Acceleration class, self.alpha is theta_ddot, self.phi_ddot is phi_ddot (for the vector itself)
#       vel_omega is theta_dot from velocity, vel_phi_dot is phi_dot from velocity.
acceleration_test_cases = [
    (
        "centripetal_xy_plane_pos_x_axis",
        1.0,
        0.0,
        np.pi / 2,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        -1.0,
        0.0,
        0.0,
    ),
    (
        "centripetal_xy_plane_pos_y_axis",
        1.0,
        np.pi / 2,
        np.pi / 2,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        -1.0,
        0.0,
    ),
    (
        "tangential_xy_plane_pos_x_axis",
        1.0,
        0.0,
        np.pi / 2,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        1.0,
        0.0,
    ),
    (
        "radial_acc_xy_plane_pos_x_axis",
        1.0,
        0.0,
        np.pi / 2,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
    ),
    (
        "zero_acceleration_input",
        1.0,
        0.0,
        np.pi / 2,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
    ),
    (
        "centripetal_xz_plane_pos_x_axis",
        1.0,
        0.0,
        np.pi / 4,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        -1 / np.sqrt(2),
        0.0,
        -1 / np.sqrt(2),
    ),
    (
        "centripetal_yz_plane_pos_y_axis",
        1.0,
        np.pi / 2,
        np.pi / 4,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        -1 / np.sqrt(2),
        -1 / np.sqrt(2),
    ),
    (
        "general_3d_acceleration",
        2.0,
        np.pi / 6,
        np.pi / 3,
        0.5,
        0.2,
        0.3,
        0.1,
        0.4,
        0.6,
        -0.18 + 0.125 * np.sqrt(3),
        0.02 * np.sqrt(3) + 1.125,
        -0.04 - 0.75 * np.sqrt(3),
    ),
]

from mechanism.vectors import Acceleration  # ensure Acceleration is imported


@pytest.mark.parametrize(
    "name, pos_r, pos_theta, pos_phi, vel_r_dot, vel_omega, vel_phi_dot, r_ddot, alpha, phi_ddot_accel, expected_ax, expected_ay, expected_az",
    acceleration_test_cases,
)
def test_acceleration_both_spherical(
    name,
    pos_r,
    pos_theta,
    pos_phi,
    vel_r_dot,
    vel_omega,
    vel_phi_dot,
    r_ddot,
    alpha,
    phi_ddot_accel,
    expected_ax,
    expected_ay,
    expected_az,
):
    """Tests Acceleration._both_spherical for various scenarios."""
    acc_vector = Acceleration(r=0, theta=0, phi=0)  # Dummy values for constructor

    # Set positional context
    acc_vector.pos_r = pos_r
    acc_vector.pos_theta = pos_theta
    acc_vector.pos_phi = pos_phi

    # Set velocity context
    acc_vector.vel_r_dot = vel_r_dot
    acc_vector.vel_omega = vel_omega  # This is theta_dot from velocity
    acc_vector.vel_phi_dot = vel_phi_dot  # This is phi_dot from velocity

    # Call the method to be tested.
    # Inputs are r_ddot, alpha (as theta_ddot_acceleration), phi_ddot_acceleration
    result_xyz = acc_vector._both_spherical(r_ddot, alpha, phi_ddot_accel)

    assert isinstance(result_xyz, np.ndarray), "Result should be a numpy array"
    assert result_xyz.shape == (3,), "Result should be a 3-element array"

    assert np.isclose(result_xyz[0], expected_ax, rtol=RTOL, atol=ATOL), (
        f"{name}: ax mismatch. Expected {expected_ax}, got {result_xyz[0]}"
    )
    assert np.isclose(result_xyz[1], expected_ay, rtol=RTOL, atol=ATOL), (
        f"{name}: ay mismatch. Expected {expected_ay}, got {result_xyz[1]}"
    )
    assert np.isclose(result_xyz[2], expected_az, rtol=RTOL, atol=ATOL), (
        f"{name}: az mismatch. Expected {expected_az}, got {result_xyz[2]}"
    )

    # Also check if the internal x, y, z of the acc_vector object are updated
    assert np.isclose(acc_vector.x, expected_ax, rtol=RTOL, atol=ATOL), (
        f"{name}: internal acc_vector.x mismatch"
    )
    assert np.isclose(acc_vector.y, expected_ay, rtol=RTOL, atol=ATOL), (
        f"{name}: internal acc_vector.y mismatch"
    )
    assert np.isclose(acc_vector.z, expected_az, rtol=RTOL, atol=ATOL), (
        f"{name}: internal acc_vector.z mismatch"
    )


if __name__ == "__main__":
    # This allows running pytest on this file directly if needed
    # e.g., python tests/mechanism/test_vectors_3d.py
    # However, typically you'd run pytest from the root directory
    pytest.main([__file__])
