import matplotlib.pyplot as plt
import numpy as np
import math
from matplotlib.patches import Circle, Polygon

# --- Parameters ------------------------------------------------------------
# Link lengths in mm (kept from previous example for consistency)
l1, l2, l3, l4 = 111, 91, 113, 156   # ground, crank, coupler, follower
theta = 2.37                          # crank angle in radians
bar_thickness = 8                     # visual thickness of each bar (mm, scaled)

# --- Geometry --------------------------------------------------------------
A = np.array([0.0, 0.0])
D = np.array([l1, 0.0])
B = np.array([l2 * math.cos(theta), l2 * math.sin(theta)])

def circle_intersections(p0, r0, p1, r1):
    dx, dy = p1 - p0
    d = math.hypot(dx, dy)
    a = (r0**2 - r1**2 + d**2) / (2 * d)
    h = math.sqrt(max(r0**2 - a**2, 0))
    xm, ym = p0 + a * (p1 - p0) / d
    xs1 = xm + h * dy / d
    ys1 = ym - h * dx / d
    xs2 = xm - h * dy / d
    ys2 = ym + h * dx / d
    return np.array([xs1, ys1]), np.array([xs2, ys2])

C_choices = circle_intersections(B, l3, D, l4)
C = max(C_choices, key=lambda p: p[1])  # take upper

points = dict(A=A, B=B, C=C, D=D)
links = [("A", "B", l2), ("B", "C", l3), ("C", "D", l4), ("A", "D", l1)]

# --- Plot ------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(9, 6))
fig.patch.set_facecolor("#0f2f57")   # deep blueprint blue
ax.set_facecolor("#0f2f57")
ax.set_aspect('equal', 'box')

# Helper to draw a "thick bar" between two points
def draw_bar(p, q, thickness, **kwargs):
    v = q - p
    length = math.hypot(*v)
    if length == 0:
        return
    # unit perpendicular
    perp = np.array([-v[1], v[0]]) / length
    offset = (thickness / 2.0) * perp
    poly = np.vstack([p + offset, q + offset, q - offset, p - offset])
    ax.add_patch(Polygon(poly, closed=True, **kwargs))

# Draw links as thick white bars
for p_lbl, q_lbl, L in links:
    draw_bar(points[p_lbl], points[q_lbl], bar_thickness, facecolor="none", edgecolor="white", linewidth=1.2)
    # annotate length at mid‑point
    mid = 0.5 * (points[p_lbl] + points[q_lbl])
    ax.text(mid[0], mid[1], f"{L} mm", color="white", fontsize=9, ha="center", va="center")

# Draw holes (⌀6 mm visual)
for lbl, coord in points.items():
    ax.add_patch(Circle(coord, 3, fill=False, edgecolor="white", linewidth=1.2))
    ax.text(coord[0], coord[1] + 7, lbl, color="white", fontsize=11, ha="center")
    ax.text(coord[0], coord[1] - 9, "⌀6 mm", color="white", fontsize=7, ha="center")

# Ground dimension arrow
ax.annotate("", xy=(A[0], -25), xytext=(D[0], -25),
            arrowprops=dict(arrowstyle="<->", color="white", linewidth=1))
ax.text((A[0]+D[0])/2, -30, f"{l1} mm (ground)", color="white", fontsize=8, ha="center")

# Formatting
ax.set_xlim(-60, l1 + 60)
ax.set_ylim(-60, max(C[1], B[1]) + 60)
ax.axis("off")
plt.title("Random 4‑Bar Linkage – Blueprint View", color="white", fontsize=14)
plt.tight_layout()
plt.show()
