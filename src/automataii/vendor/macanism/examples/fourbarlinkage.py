from mechanism import *
import numpy as np
import matplotlib.pyplot as plt

# Joint.follow_all = True  # You can trace the path of all joints by uncommenting this

O, A, B, C, D = get_joints("O A B C D")
D.follow = True
B.follow = True

a = Vector((O, A), r=5)
# b = Vector((O, C), r=8, theta=np.deg2rad(90), style='ground')  # Use this vector for a cusp output
b = Vector((O, C), r=8, theta=0, style="ground")
c = Vector((A, B), r=8)
d = Vector((C, B), r=9)
e = Vector((A, D), r=4)
f = Vector((O, D), show=False)


def loops(x, inp):
    # Note: The way this is structured with the second loop equation is only appropriate for position analysis.
    # MODIFIED for 3D framework, but returning only X, Y components for the planar 4 unknowns.
    # Loop 1: O->A->B->C->O => a + c - d - b = 0
    loop1_vec_sum = a(inp) + c(x[0]) - d(x[1]) - b()  # Gets [x,y,z]

    # Loop 2: O->A->D->O => a + e - f = 0
    const_angle = np.deg2rad(30)
    loop2_vec_sum = a(inp) + e(x[0] + const_angle) - f(x[2], x[3])  # Gets [x,y,z]

    # Return flattened array of X, Y components only [L1x, L1y, L2x, L2y]
    # Total 4 equations for 4 unknowns (th_c, th_d, r_f, th_f).
    return np.array(
        [loop1_vec_sum[0], loop1_vec_sum[1], loop2_vec_sum[0], loop2_vec_sum[1]]
    )


t2 = np.linspace(0, 6 * np.pi, 300)
guess = np.concatenate((np.deg2rad([50, 120]), np.array([5]), np.deg2rad([50])))
mechanism = Mechanism(
    vectors=(a, b, c, d, e, f), origin=O, pos=t2, guess=(guess,), loops=loops
)

mechanism.iterate()
ani, fig, ax = mechanism.get_animation()

ax.set_title("Four Bar Linkage")

plt.show()

# ani.save('../animations/fourbarlinkage.mp4', dpi=300)
