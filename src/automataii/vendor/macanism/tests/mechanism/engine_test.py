# This test just verifies that the directions of the velocity and acceleration makes sense.
# See to it that the figures match those from Homework 2
from mechanism import *
import numpy as np
import matplotlib.pyplot as plt

O, A, B, C, D = get_joints("O A B C D")
C.follow = True
a = Vector((O, A), r=2)
b = Vector((A, B), r=6)
x = Vector((O, B), theta=np.pi / 3, style="dotted")
c = Vector((A, C), r=2)
y = Vector((C, D), r=5)
d = Vector((O, D), theta=2 * np.pi / 3, style="dotted")
e = Vector((C, B), r=6)


# 0: t3, 1: t4, 2: t5, 3: t6, 4: x, 5: d
def loops(t, inp):
    # Calculate the 3D vector result for each loop equation
    # Note: The original code seemed to imply 3 loops, but the calculation
    # only used 3 rows in `temp`. Assuming 3 equations.
    # Equation 1: a + b - x = 0  (Loop O-A-B-O)
    # Equation 2: e - b + c = 0  (Loop C-B-A-C? Seems odd, maybe A-B-C-A or O-A-C-O? Needs mech diagram)
    # Equation 3: d - y - c - a = 0 (Loop O-D-C-A-O?)
    # Assuming these equations represent closures back to origin or fixed points.

    # Get vector components (which are now 3D arrays [x,y,z])
    # Input 'a' is driven by 'inp' (presumably angle)
    vec_a_xyz = inp  # inp already contains [x,y,z] components of the driven vector 'a'
    # Unknowns 'b', 'c', 'e', 'y', 'x', 'd'
    # t[0]=theta_b, t[1]=theta_c, t[2]=theta_y, t[3]=theta_e, t[4]=r_x, t[5]=r_d
    vec_b_xyz = b(t[0])
    vec_c_xyz = c(t[1])
    vec_d_xyz = d(t[5])  # Vector d seems to vary in length? Or t[5] is angle?
    # Based on init `d = Vector((O, D), theta=2*np.pi/3, style='dotted')`,
    # theta is fixed, so t[5] must be r (length). `get` should be `_slip`.
    vec_e_xyz = e(t[3])
    vec_x_xyz = x(
        t[4]
    )  # Vector x init `x = Vector((O, B), theta=np.pi/3, style='dotted')`,
    # theta is fixed, so t[4] must be r (length). `get` should be `_slip`.
    vec_y_xyz = y(t[2])

    # Calculate residuals for each equation (result is a 3D vector)
    eq1_res = vec_a_xyz + vec_b_xyz - vec_x_xyz
    eq2_res = vec_e_xyz - vec_b_xyz + vec_c_xyz
    eq3_res = vec_d_xyz - vec_y_xyz - vec_c_xyz - vec_a_xyz

    # For a planar mechanism simulated in 3D, we only care about x and y residuals.
    # The z residuals should ideally be zero.
    # Return the flattened array of x, y residuals (6 total).
    residuals_xy = np.array(
        [
            eq1_res[0],
            eq1_res[1],  # Eq1: x, y
            eq2_res[0],
            eq2_res[1],  # Eq2: x, y
            eq3_res[0],
            eq3_res[1],  # Eq3: x, y
        ]
    )

    return residuals_xy


guess1 = np.concatenate(
    (np.deg2rad([70, 160, 120, 60]), np.array([5, 5]))
)  # 6 unknowns
guess2 = np.array([20 * np.pi, 20 * np.pi, 20 * np.pi, 20 * np.pi, 100, 100])
guess3 = np.array([100, 100, 100, 100, 100, 100])

# Testing the first iteration
# mechanism = Mechanism(vectors=(a, b, c, d, e, x, y), input_vector=a, guess=(guess1, guess2, guess3), pos=0,
#                       vel=-50*np.pi, acc=0, loops=loops)
# mechanism.calculate()
# mechanism.tables(position=True, velocity=True, acceleration=True)
# mechanism.plot(velocity=True, acceleration=True)

time = np.linspace(0, 0.04, 250)
t2_t = -50 * np.pi * time
w2_t = -50 * np.pi * np.ones(250)
a2_t = np.zeros(250)

mechanism = Mechanism(
    vectors=(a, b, c, d, e, x, y),
    origin=O,
    guess=(guess1, guess2, guess3),
    pos=t2_t,
    vel=w2_t,
    acc=a2_t,
    loops=loops,
)
mechanism.iterate()
ani, fig, ax = mechanism.get_animation(
    velocity=True, acceleration=True, stamp=time, stamp_loc=(0.5, 0.9), cushion=0.5
)

ax.set_title("Engine")

# ani.save('../animations/engine.mp4', dpi=300)

# If interested at a certain point, access the Joint attributes.
fig2, ax2 = plt.subplots()
ax2.plot(time, d.acc.r_ddots, color="maroon", label=r"$a_D(t)$")

fig3, ax3 = plt.subplots()
ax3.plot(time, C.acc_mags, color="maroon", label=r"$a_C(t)$")
ax3.plot(time, x.acc.r_ddots, color="deepskyblue", label=r"$a_B(t)$")

for ax_ in [ax2, ax3]:
    ax_.grid()
    ax_.legend()
    ax_.set_xlabel("Time ($s$)")

plt.show()
