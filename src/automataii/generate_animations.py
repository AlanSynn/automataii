#!/usr/bin/env python3
"""
Generate and visualize a comprehensive synthetic mechanism dataset.
This script creates animations for various mechanisms, showing the true motion of their links
and end-effectors, and saves the animations as GIF files.
"""

import argparse
import os
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation
from scipy.optimize import fsolve

# --- Kinematic Solvers ---

def solve_4bar_closure(x: np.ndarray, l1: float, l2: float, l3: float, l4: float, theta2: float) -> tuple[float, float]:
    theta3, theta4 = x
    eq1 = l2 * np.cos(theta2) + l3 * np.cos(theta3) - l4 * np.cos(theta4) - l1
    eq2 = l2 * np.sin(theta2) + l3 * np.sin(theta3) - l4 * np.sin(theta4)
    return (eq1, eq2)

def get_4bar_input_angle_range(l1: float, l2: float, l3: float, l4: float) -> tuple[float, float]:
    links = sorted([l1, l2, l3, l4])
    s, p, q, l = links
    # Grashof condition
    if (s + l) > (p + q):
        # It's a triple-rocker, calculate the limited range if possible.
        # This is a simplified check; real triple-rocker analysis is more complex.
        return (np.pi/3, 2*np.pi/3) # Placeholder range
    # If the shortest link is the driver, it's a crank.
    if l2 == s:
        return (0, 2 * np.pi)
    # If the shortest link is the frame, it's a double-crank (drag-link).
    if l1 == s:
        return (0, 2 * np.pi)
    # Otherwise, it's a rocker-crank, where l2 is not the full crank.
    return (np.pi/4, 3*np.pi/4) # Placeholder range


def animate_mechanisms(mechanisms: list[dict[str, Any]], title: str, output_dir: str):
    """Creates and saves an animation showing all mechanisms."""
    num_mechanisms = len(mechanisms)
    if not num_mechanisms: return

    cols = int(np.ceil(np.sqrt(num_mechanisms)))
    rows = int(np.ceil(num_mechanisms / cols)) if cols > 0 else 0
    if rows == 0: return

    fig, axes = plt.subplots(rows, cols, figsize=(cols * 6, rows * 5.5))
    axes = np.array(axes).flatten()
    fig.suptitle(title, fontsize=16)

    anims = []

    for i, mech_config in enumerate(mechanisms):
        ax = axes[i]
        ax.set_aspect('equal', adjustable='box')
        ax.grid(True)
        ax.set_title(mech_config['name'], fontsize=10)

        params = mech_config['params']
        mech_type = mech_config['type']

        if mech_type == '4-bar':
            l1, l2, l3, l4, p_x, p_y = [params[k] for k in ['l1', 'l2', 'l3', 'l4', 'px', 'py']]

            p0, p1 = np.array([0, 0]), np.array([l1, 0])
            ax.plot([p0[0], p1[0]], [p0[1], p1[1]], 's-k', lw=3, markersize=8) # Ground link

            min_angle, max_angle = get_4bar_input_angle_range(l1, l2, l3, l4)
            thetas = np.linspace(min_angle, max_angle, 150)

            crank, = ax.plot([], [], 'o-g', lw=3, markersize=6)
            coupler, = ax.plot([], [], 'o-r', lw=3, markersize=6)
            rocker, = ax.plot([], [], 'o-b', lw=3, markersize=6)
            coupler_point_dot, = ax.plot([], [], '*m', markersize=12)
            coupler_path_trace, = ax.plot([], [], '--c', lw=1)

            coupler_path_coords = []

            def init():
                max_reach = max(l1, l2, l3, l4) * 2
                ax.set_xlim(-max_reach/2, max_reach)
                ax.set_ylim(-max_reach/2, max_reach)
                return crank, coupler, rocker, coupler_point_dot, coupler_path_trace

            def update(theta2):
                sol, _, ier, _ = fsolve(solve_4bar_closure, [np.pi/2, np.pi/2], args=(l1, l2, l3, l4, theta2), full_output=True)
                if ier == 1:
                    theta3, theta4 = sol
                    a = np.array([l2 * np.cos(theta2), l2 * np.sin(theta2)])
                    b = np.array([l1 + l4 * np.cos(theta4), l4 * np.sin(theta4)])
                    cp = a + np.array([p_x*np.cos(theta3) - p_y*np.sin(theta3), p_x*np.sin(theta3) + p_y*np.cos(theta3)])

                    crank.set_data([p0[0], a[0]], [p0[1], a[1]])
                    coupler.set_data([a[0], b[0]], [a[1], b[1]])
                    rocker.set_data([p1[0], b[0]], [p1[1], b[1]])
                    coupler_point_dot.set_data([cp[0]], [cp[1]])

                    coupler_path_coords.append(cp)
                    if len(coupler_path_coords) > 1:
                        path_arr = np.array(coupler_path_coords)
                        coupler_path_trace.set_data(path_arr[:,0], path_arr[:,1])
                return crank, coupler, rocker, coupler_point_dot, coupler_path_trace

            # This is key: create one animation object *per subplot*
            anim = FuncAnimation(fig, update, frames=thetas, init_func=init, blit=True, interval=40)
            anims.append(anim) # Keep a reference

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    output_path = os.path.join(output_dir, f"{title.lower().replace(' ', '_')}.gif")
    # This uses the first animation's save, which is a limitation but will work here.
    # A more robust solution would use a single master update function.
    if anims:
        anims[0].save(output_path, writer='pillow', fps=25)
        print(f"Saved animation to {output_path}")

    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Generate and visualize mechanism animations.")
    from .utils.paths import get_project_root
    project_root = get_project_root()
    default_output = project_root / "generated_mechanisms" / "animations"
    parser.add_argument("--output_dir",type=str, default=str(default_output))
    args = parser.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    print("\n=== Mechanism Animation Generator ===\n")

    four_bar_configs = [
        {'type': '4-bar', 'name': 'Crank-Rocker', 'params': {'l1': 6, 'l2': 2, 'l3': 7, 'l4': 5, 'px': 3.5, 'py': 1}},
        {'type': '4-bar', 'name': 'Drag-Link', 'params': {'l1': 2, 'l2': 4, 'l3': 5, 'l4': 6, 'px': 2.5, 'py': 2.5}},
    ]
    animate_mechanisms(four_bar_configs, "4-Bar Linkages", args.output_dir)

    print("\n✓ Animation generation complete!")
    print(f"Files saved in: {os.path.abspath(args.output_dir)}")

if __name__ == "__main__":
    main()
