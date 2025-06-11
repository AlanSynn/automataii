#!/usr/bin/env python3
"""
Generate and visualize a comprehensive synthetic mechanism dataset.
This script creates animations for 4-bar linkages, cam-followers, and gear trains,
and also generates a single JSON dataset file with their path data.
"""

import os
import json
import numpy as np
import argparse
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from typing import List, Dict, Any, Tuple
from scipy.optimize import fsolve

# --- UTILITIES ---

def normalize_path(path_coords: List[List[float]], target_bounds: Tuple[float, float] = (-1.0, 1.0)) -> List[List[float]]:
    """Normalize path coordinates to fit within target bounds."""
    if not path_coords: return []
    coords_array = np.array(path_coords)
    min_vals, max_vals = coords_array.min(axis=0), coords_array.max(axis=0)
    ranges = max_vals - min_vals
    ranges[ranges == 0] = 1
    normalized = (coords_array - min_vals) / ranges
    return (normalized * (target_bounds[1] - target_bounds[0]) + target_bounds[0]).tolist()

# --- KINEMATIC SIMULATORS ---

def solve_4bar_closure(x, l1, l2, l3, l4, theta2):
    theta3, theta4 = x
    return (l2*np.cos(theta2) + l3*np.cos(theta3) - l4*np.cos(theta4) - l1,
            l2*np.sin(theta2) + l3*np.sin(theta3) - l4*np.sin(theta4))

def simulate_4bar_motion(l1, l2, l3, l4, p_x, p_y, num_steps=180):
    """Simulates a 4-bar linkage, returning data needed for animation and dataset."""
    sim_data = []
    last_sol = [np.pi/2, np.pi/2]
    for theta2 in np.linspace(0, 2*np.pi, num_steps):
        sol, _, ier, _ = fsolve(solve_4bar_closure, last_sol, args=(l1, l2, l3, l4, theta2), full_output=True)
        if ier == 1:
            last_sol = sol
            theta3, theta4 = sol
            p_a = np.array([l2*np.cos(theta2), l2*np.sin(theta2)])
            p_b = np.array([l1 + l4*np.cos(theta4), l4*np.sin(theta4)])
            p_coupler = p_a + np.array([p_x*np.cos(theta3) - p_y*np.sin(theta3), p_x*np.sin(theta3) + p_y*np.cos(theta3)])
            sim_data.append({'p_a': p_a, 'p_b': p_b, 'p_coupler': p_coupler})
    return sim_data

def simulate_cam_motion(base_radius, eccentricity, num_steps=180):
    """Simulates a cam-follower, returning data for animation."""
    sim_data = []
    cam_offset = np.array([eccentricity, 0])
    for theta in np.linspace(0, 2*np.pi, num_steps):
        rot = np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]])
        rotated_center = rot @ cam_offset
        follower_y = rotated_center[1] + base_radius
        sim_data.append({'cam_center': rotated_center, 'follower_y': follower_y})
    return sim_data

def simulate_gear_motion(r1, r2, num_steps=180):
    """Simulates a gear train, returning data for animation."""
    sim_data = []
    for theta1 in np.linspace(0, 2*np.pi, num_steps):
        sim_data.append({'t1': theta1, 't2': -theta1 * (r1 / r2)})
    return sim_data

# --- CONFIGURATION GENERATORS ---

def generate_crank_rocker_configs(num_configs: int, max_dim: float = 100.0) -> List[Dict[str, Any]]:
    """Generates a list of diverse, valid Crank-Rocker configurations."""
    configs = []
    attempts = 0
    while len(configs) < num_configs and attempts < 500:
        attempts += 1
        # Generate link lengths based on the assumed space
        l1 = np.random.uniform(0.3 * max_dim, 0.7 * max_dim)  # Ground link
        l2 = np.random.uniform(0.1 * max_dim, 0.25 * max_dim) # Crank
        l3 = np.random.uniform(0.5 * max_dim, 1.2 * max_dim)  # Coupler
        l4 = np.random.uniform(0.5 * max_dim, 1.2 * max_dim)  # Follower

        # Ensure Grashof Crank-Rocker conditions are met
        links = {'l1': l1, 'l2': l2, 'l3': l3, 'l4': l4}
        s_link_name = min(links, key=links.get)

        # Condition 1: Crank (l2) must be the shortest link
        if s_link_name != 'l2':
            continue

        # Condition 2: Grashof condition (s + l <= p + q)
        s, l = links[s_link_name], max(links.values())
        p_q_sum = sum(links.values()) - s - l
        if s + l > p_q_sum:
            continue

        # Generate a coupler point for an interesting path
        p_x = np.random.uniform(l3 * 0.2, l3 * 0.8)
        p_y = np.random.uniform(-l3 * 0.5, l3 * 0.5)

        configs.append({
            'type': '4-bar',
            'name': f'Crank-Rocker #{len(configs) + 1}',
            'params': {'l1': l1, 'l2': l2, 'l3': l3, 'l4': l4, 'p_x': p_x, 'p_y': p_y}
        })

    print(f"Generated {len(configs)} diverse Crank-Rocker configurations.")
    return configs

# --- VISUALIZATION & DATASET GENERATION ---

def process_mechanisms(configs: List[Dict[str, Any]], title: str, output_dir: str, dataset_aggregator: List):
    """Generates an animation and dataset entries for a list of mechanism configs."""
    num_mechs = len(configs)
    if not num_mechs: return

    fig, axes = plt.subplots(1, num_mechs, figsize=(num_mechs * 6, 6))
    axes = np.array(axes).flatten()
    fig.suptitle(title, fontsize=16)

    anim_funcs = []
    for i, config in enumerate(configs):
        ax = axes[i]
        ax.set_aspect('equal', adjustable='box')
        ax.grid(True)
        ax.set_title(config['name'], fontsize=10)
        params, mech_type = config['params'], config['type']

        if mech_type == '4-bar':
            sim_data = simulate_4bar_motion(**params)
            path = np.array([f['p_coupler'] for f in sim_data])
            dataset_aggregator.append({"type": "4-bar Coupler", "name": f"4-bar {config['name']}", "parameters": params, "path_coordinates": normalize_path(path.tolist()), "key_points": {"ground_pivot_1": [0,0], "ground_pivot_2": [params['l1'],0], "coupler_point_path": path.tolist()}})

            p0, p1 = np.array([0, 0]), np.array([params['l1'], 0])
            ax.plot(path[:,0], path[:,1], '--m', lw=1.5)
            driver, = ax.plot([], [], 'o-', color='orange', lw=5)
            follower, = ax.plot([], [], 'o-', color='gold', lw=5)
            coupler, = ax.plot([], [], 'o-', color='green', lw=3)
            coupler_point_marker, = ax.plot([], [], 'o', color='red', markersize=8)

            def create_4bar_anim(sd, dr, fo, co, cpm):
                def init():
                    all_x = np.concatenate([path[:, 0], [p0[0], p1[0]]])
                    all_y = np.concatenate([path[:, 1], [p0[1], p1[1]]])
                    padding = 5
                    ax.set_xlim(all_x.min() - padding, all_x.max() + padding)
                    ax.set_ylim(all_y.min() - padding, all_y.max() + padding)
                    return dr, fo, co, cpm
                def update(idx):
                    frame = sd[idx]
                    p_a, p_b, p_coupler_pos = frame['p_a'], frame['p_b'], frame['p_coupler']
                    dr.set_data([p0[0], p_a[0]], [p0[1], p_a[1]])
                    fo.set_data([p1[0], p_b[0]], [p1[1], p_b[1]])
                    co.set_data([p_a[0], p_b[0], p_coupler_pos[0], p_a[0]],
                                [p_a[1], p_b[1], p_coupler_pos[1], p_a[1]])
                    cpm.set_data([p_coupler_pos[0]], [p_coupler_pos[1]])
                    return dr, fo, co, cpm
                return init, update
            init, update = create_4bar_anim(sim_data, driver, follower, coupler, coupler_point_marker)
            anim_funcs.append({'init': init, 'update': update, 'frames': len(sim_data)})

        elif mech_type == 'cam-follower':
            sim_data = simulate_cam_motion(**params)
            path = np.array([[0, f['follower_y']] for f in sim_data])
            dataset_aggregator.append({"type": "Cam Follower", "name": f"Cam {config['name']}", "parameters": params, "path_coordinates": normalize_path(path.tolist())})

            ax.plot(path[:, 0], path[:, 1], '--c', lw=2)

            r = params['base_radius']
            profile = ax.fill([], [], 'deepskyblue')[0]
            follower = ax.fill([], [], 'seagreen')[0]

            def create_cam_anim(sd, prof, foll):
                def init():
                    ys = [f['follower_y'] for f in sd]
                    ax.set_xlim(-r-5, r+5); ax.set_ylim(min(ys)-5, max(ys)+5)
                    return prof, foll
                def update(idx):
                    frame = sd[idx]
                    angles = np.linspace(0,2*np.pi,100)
                    prof.set_xy(np.c_[frame['cam_center'][0]+r*np.cos(angles), frame['cam_center'][1]+r*np.sin(angles)])
                    y, w, h = frame['follower_y'], r, r/2
                    foll.set_xy([(-w/2,y),(w/2,y),(w/2,y+h),(-w/2,y+h)])
                    return prof, foll
                return init, update
            init, update = create_cam_anim(sim_data, profile, follower)
            anim_funcs.append({'init': init, 'update': update, 'frames': len(sim_data)})

        elif mech_type == 'gear-train':
            sim_data = simulate_gear_motion(**params)
            r1, r2 = params['r1'], params['r2']
            path = np.array([[r1*np.cos(f['t1']), r1*np.sin(f['t1'])] for f in sim_data]) # Path on driver gear
            dataset_aggregator.append({"type": "Gear Contact", "name": f"Gear {config['name']}", "parameters": params, "path_coordinates": normalize_path(path.tolist())})

            p1, p2 = np.array([-r1,0]), np.array([r2,0])
            ax.add_patch(plt.Circle(p1,r1,color='slategray')); ax.add_patch(plt.Circle(p2,r2,color='coral'))
            line1, = ax.plot([],[],'w-'); line2, = ax.plot([],[],'w-')

            def create_gear_anim(sd, l1, l2):
                def init():
                    ax.set_xlim(-r1-r2-1,r1+r2+1); ax.set_ylim(-max(r1,r2)-1, max(r1,r2)+1)
                    return l1, l2
                def update(idx):
                    frame = sd[idx]
                    l1.set_data([p1[0], p1[0]+r1*np.cos(frame['t1'])],[p1[1], p1[1]+r1*np.sin(frame['t1'])])
                    l2.set_data([p2[0], p2[0]+r2*np.cos(frame['t2'])],[p2[1], p2[1]+r2*np.sin(frame['t2'])])
                    return l1, l2
                return init, update
            init, update = create_gear_anim(sim_data, line1, line2)
            anim_funcs.append({'init': init, 'update': update, 'frames': len(sim_data)})

    def master_update(frame_index):
        artists = []
        for funcs in anim_funcs:
            artists.extend(funcs['update'](frame_index % funcs['frames']))
        return artists

    for funcs in anim_funcs: funcs['init']()
    anim = FuncAnimation(fig, master_update, frames=180, interval=50, blit=True)
    anim.save(os.path.join(output_dir, f"{title.lower().replace(' ', '_')}.gif"), writer='pillow', fps=20)
    plt.close(fig)
    print(f"Saved animation: {title}.gif")

def main():
    parser = argparse.ArgumentParser(description="Generate and visualize mechanism datasets.")
    base_dir = os.path.join(os.path.dirname(__file__), "..", "..", "generated_mechanisms")
    parser.add_argument("--output_dir", type=str, default=os.path.join(base_dir, "animations"))
    args = parser.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    print("\n=== Mechanism Animation and Dataset Generator ===\n")
    all_mechanisms_data = []

    # --- Configurations ---
    crank_rocker_configs = generate_crank_rocker_configs(4) # Generate 4 diverse configs

    cam_configs = [{'type': 'cam-follower', 'name': 'Eccentric Cam', 'params': {'base_radius': 25.0, 'eccentricity': 10.0}}]
    gear_configs = [{'type': 'gear-train', 'name': 'Simple Gear Train', 'params': {'r1': 30, 'r2': 50}}]

    # --- Generation ---
    if crank_rocker_configs:
        process_mechanisms(crank_rocker_configs, "4-Bar Crank-Rocker Linkages", args.output_dir, all_mechanisms_data)
    if cam_configs:
        process_mechanisms(cam_configs, "Cam-Follower Mechanisms", args.output_dir, all_mechanisms_data)
    if gear_configs:
        process_mechanisms(gear_configs, "Planar Gear Trains", args.output_dir, all_mechanisms_data)

    # --- Save Dataset ---
    dataset_path = os.path.join(os.path.dirname(__file__), "..", "kinematics", "generated_mechanism_paths.json")
    os.makedirs(os.path.dirname(dataset_path), exist_ok=True)
    print(f"\nSaving dataset with {len(all_mechanisms_data)} mechanisms to: {dataset_path}")
    with open(dataset_path, 'w') as f:
        json.dump(all_mechanisms_data, f, indent=2)

    print("\n✓ Generation complete!")

if __name__ == "__main__":
    main()