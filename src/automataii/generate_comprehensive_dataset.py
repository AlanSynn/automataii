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

def normalize_path(path_coords: List[List[float]], target_bounds: Tuple[float, float] = (-1.0, 1.0)) -> Tuple[List[List[float]], Dict]:
    """Normalize path coordinates and return normalization parameters for reconstruction."""
    if not path_coords: return [], {}
    coords_array = np.array(path_coords)
    min_vals, max_vals = coords_array.min(axis=0), coords_array.max(axis=0)
    center = (min_vals + max_vals) / 2
    ranges = max_vals - min_vals
    ranges[ranges == 0] = 1
    max_range = np.max(ranges)

    # Normalize keeping aspect ratio
    normalized = (coords_array - center) / (max_range / 2)

    # Store normalization parameters for reconstruction
    norm_params = {
        "center": center.tolist(),
        "scale": max_range / 2,
        "original_bounds": [min_vals.tolist(), max_vals.tolist()]
    }

    return normalized.tolist(), norm_params

# --- KINEMATIC SIMULATORS ---

def solve_4bar_closure(x, l1, l2, l3, l4, theta2):
    theta3, theta4 = x
    return (l2*np.cos(theta2) + l3*np.cos(theta3) - l4*np.cos(theta4) - l1,
            l2*np.sin(theta2) + l3*np.sin(theta3) - l4*np.sin(theta4))

def simulate_4bar_motion(l1, l2, l3, l4, p_x, p_y, num_steps=180):
    """Simulates a 4-bar linkage, returning data needed for animation and dataset."""
    sim_data = []
    last_sol = [np.pi/2, np.pi/2]

    # Ground pivots
    p1 = np.array([0, 0])           # Fixed ground pivot 1
    p2 = np.array([l1, 0])          # Fixed ground pivot 2

    for theta2 in np.linspace(0, 2*np.pi, num_steps):
        sol, _, ier, _ = fsolve(solve_4bar_closure, last_sol, args=(l1, l2, l3, l4, theta2), full_output=True)
        if ier == 1:
            last_sol = sol
            theta3, theta4 = sol

            # Calculate moving joint positions
            p3 = p1 + np.array([l2*np.cos(theta2), l2*np.sin(theta2)])  # Moving joint connected to p1
            p4 = p2 + np.array([l4*np.cos(theta4), l4*np.sin(theta4)])  # Moving joint connected to p2

            # Calculate coupler point position relative to the coupler link (p3-p4)
            coupler_vec = p4 - p3
            coupler_length = np.linalg.norm(coupler_vec)
            if coupler_length > 0:
                coupler_unit = coupler_vec / coupler_length
                coupler_normal = np.array([-coupler_unit[1], coupler_unit[0]])
                p_coupler = p3 + p_x * coupler_unit + p_y * coupler_normal
            else:
                p_coupler = p3

            sim_data.append({
                'p1': p1, 'p2': p2, 'p3': p3, 'p4': p4,
                'p_coupler': p_coupler,
                'theta2': theta2, 'theta3': theta3, 'theta4': theta4
            })
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
    gear1_center = np.array([0, 0])
    gear2_center = np.array([r1 + r2, 0])

    for theta1 in np.linspace(0, 2*np.pi, num_steps):
        theta2 = -theta1 * (r1 / r2)  # Gear ratio

        # Calculate tracking point on gear 1 circumference
        tracking_point = gear1_center + np.array([r1 * np.cos(theta1), r1 * np.sin(theta1)])

        sim_data.append({
            't1': theta1,
            't2': theta2,
            'gear1_center': gear1_center,
            'gear2_center': gear2_center,
            'tracking_point': tracking_point
        })
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

    # Add a specific case with the coupler point on the link center
    if len(configs) > 0:
        configs[0]['name'] = 'Crank-Rocker (Center Coupler)'
        configs[0]['params']['p_x'] = configs[0]['params']['l3'] / 2
        configs[0]['params']['p_y'] = 0

    print(f"Generated {len(configs)} diverse Crank-Rocker configurations.")
    return configs

# --- VISUALIZATION & DATASET GENERATION ---

def process_mechanisms(configs: List[Dict[str, Any]], title: str, output_dir: str, dataset_aggregator: List):
    """Generates an animation and dataset entries for a list of mechanism configs."""
    num_mechs = len(configs)
    if not num_mechs: return

    fig, axes = plt.subplots(1, num_mechs, figsize=(num_mechs * 8, 8))
    axes = np.array(axes).flatten()
    fig.suptitle(title, fontsize=20)

    anim_funcs = []
    for i, config in enumerate(configs):
        ax = axes[i]
        ax.set_aspect('equal', adjustable='box')
        ax.grid(True)
        ax.set_title(config['name'], fontsize=12)
        params, mech_type = config['params'], config['type']

        if mech_type == '4-bar':
            # Add text annotations for link lengths and coupler point
            l1, l2, l3, l4 = params['l1'], params['l2'], params['l3'], params['l4']
            p_x, p_y = params['p_x'], params['p_y']
            info_text = (
                f"l1 (ground): {l1:.1f}\n"
                f"l2 (crank): {l2:.1f}\n"
                f"l3 (coupler): {l3:.1f}\n"
                f"l4 (rocker): {l4:.1f}\n"
                f"Coupler Pt (x,y): ({p_x:.1f}, {p_y:.1f})"
            )
            ax.text(0.05, 0.95, info_text, transform=ax.transAxes, fontsize=9,
                    verticalalignment='top', bbox=dict(boxstyle='round,pad=0.5', fc='wheat', alpha=0.5))
            sim_data = simulate_4bar_motion(**params)
            path = np.array([f['p_coupler'] for f in sim_data])

            # Get complete mechanism geometry
            first_frame = sim_data[0]
            p1, p2 = first_frame['p1'], first_frame['p2']
            p3, p4 = first_frame['p3'], first_frame['p4']

            # Normalize path and get parameters
            normalized_path, norm_params = normalize_path(path.tolist())

            # Calculate all mechanism points for bounding box
            all_points = np.vstack([path, np.array([p1, p2, p3, p4])])
            mech_center = np.mean(all_points, axis=0)
            mech_extent = np.max(np.abs(all_points - mech_center))

            # Calculate coupler path in the same coordinate system
            coupler_path = [f['p_coupler'] for f in sim_data]

            # Calculate coupler point at initial position for reference
            initial_coupler = sim_data[0]['p_coupler']

            dataset_entry = {
                "type": "4-bar Coupler",
                "name": f"4-bar {config['name']}",
                "parameters": {
                    **params,
                    "coupler_point": {"x": params['p_x'], "y": params['p_y']}  # Explicit coupler point
                },
                "path_coordinates": normalized_path,
                "path_normalization": norm_params,  # Store normalization info
                "key_points": {
                    "ground_pivot_1": p1.tolist(),
                    "ground_pivot_2": p2.tolist(),
                    "initial_moving_joint_1": p3.tolist(),
                    "initial_moving_joint_2": p4.tolist(),
                    "coupler_point_offset": {"x": params['p_x'], "y": params['p_y']},
                    "initial_coupler_position": initial_coupler.tolist()  # Where coupler starts
                },
                "skeleton_attachment": {
                    "attachment_point": "coupler_point",  # This is what follows the skeleton
                    "attachment_coordinates": initial_coupler.tolist(),  # Initial position
                    "description": "The coupler point moves along the generated path and drives skeleton animation"
                },
                "mechanism_layout": {
                    "description": (
                        "A 4-bar linkage consisting of a ground link (l1), an input crank (l2), "
                        "a coupler link (l3), and an output rocker (l4). The input crank (l2) rotates fully, "
                        "driving the mechanism. The path is traced by a point on a triangular coupler plate, "
                        "defined by the vertices (p3, p4, and the coupler point). "
                        "The coupler point's position is defined by an offset (p_x, p_y) relative to the coupler link's local "
                        "coordinate system, where the origin is at joint p3 and the x-axis points towards p4."
                    ),
                    "link_roles": {
                        "l1": {"name": "ground_link", "connects": ["p1", "p2"], "fixed": True},
                        "l2": {"name": "input_crank", "connects": ["p1", "p3"], "driver": True},
                        "l3": {"name": "coupler_plate", "connects": ["p3", "p4", "coupler_point"], "carries_point": True},
                        "l4": {"name": "output_rocker", "connects": ["p4", "p2"], "driven": True}
                    },
                    "coordinate_system": {
                        "origin": "ground_pivot_1 (p1)",
                        "x_axis": "along ground link towards p2",
                        "units": "arbitrary length units"
                    }
                },
                "visualization_params": {
                    "center": mech_center.tolist(),
                    "scale": float(mech_extent),
                    "bounding_box": {
                        "min": np.min(all_points, axis=0).tolist(),
                        "max": np.max(all_points, axis=0).tolist()
                    }
                },
                "full_simulation_data": {
                    "coupler_path": [cp.tolist() for cp in coupler_path],
                    "link_lengths": {"l1": params['l1'], "l2": params['l2'], "l3": params['l3'], "l4": params['l4']},
                    "joint_positions": {
                        "p1_positions": [f['p1'].tolist() for f in sim_data],  # Ground pivot 1 (fixed)
                        "p2_positions": [f['p2'].tolist() for f in sim_data],  # Ground pivot 2 (fixed)
                        "p3_positions": [f['p3'].tolist() for f in sim_data],  # Moving joint (crank end)
                        "p4_positions": [f['p4'].tolist() for f in sim_data],  # Moving joint (rocker end)
                        "coupler_positions": [f['p_coupler'].tolist() for f in sim_data]  # The point that follows path
                    },
                    "angles": {
                        "theta2": [f['theta2'] for f in sim_data],  # Input crank angle
                        "theta3": [f['theta3'] for f in sim_data],  # Coupler link angle
                        "theta4": [f['theta4'] for f in sim_data]   # Output rocker angle
                    }
                }
            }
            dataset_aggregator.append(dataset_entry)
            print(f"Added 4-bar dataset entry with keys: {list(dataset_entry.keys())}")
            print(f"Key points: {list(dataset_entry['key_points'].keys())}")

            ground_p1, ground_p2 = first_frame['p1'], first_frame['p2']
            ax.plot(path[:,0], path[:,1], '--m', lw=1.5)
            driver, = ax.plot([], [], 'o-', color='orange', lw=5)
            follower, = ax.plot([], [], 'o-', color='gold', lw=5)

            # Visualize coupler dynamically as a line or triangle
            coupler_poly = plt.Polygon([[0,0],[0,0],[0,0]], fc='lightgreen', alpha=0.8, zorder=2, visible=False)
            coupler_line, = ax.plot([], [], '-', color='lightgreen', lw=4, zorder=2, visible=False)
            ax.add_patch(coupler_poly)
            coupler_point_marker, = ax.plot([], [], 'o', color='red', markersize=8, zorder=3)


            def create_4bar_anim(sd, dr, fo, cpoly, cline, cpm):
                def init():
                    all_x = np.concatenate([path[:, 0], [ground_p1[0], ground_p2[0]]])
                    all_y = np.concatenate([path[:, 1], [ground_p1[1], ground_p2[1]]])
                    padding = 5
                    ax.set_xlim(all_x.min() - padding, all_x.max() + padding)
                    ax.set_ylim(all_y.min() - padding, all_y.max() + padding)
                    return dr, fo, cpoly, cline, cpm
                def update(idx):
                    frame = sd[idx]
                    p1, p2, p3, p4 = frame['p1'], frame['p2'], frame['p3'], frame['p4']
                    p_coupler_pos = frame['p_coupler']
                    dr.set_data([p1[0], p3[0]], [p1[1], p3[1]])
                    fo.set_data([p2[0], p4[0]], [p2[1], p4[1]])

                    # Check for collinearity to decide visualization
                    # Area of triangle using cross-product. If area is near zero, points are collinear.
                    area = np.abs(p3[0]*(p4[1]-p_coupler_pos[1]) + p4[0]*(p_coupler_pos[1]-p3[1]) + p_coupler_pos[0]*(p3[1]-p4[1])) / 2
                    if area < 1e-3: # Treat as collinear
                        cpoly.set_visible(False)
                        cline.set_visible(True)
                        cline.set_data([p3[0], p4[0]], [p3[1], p4[1]])
                    else: # Treat as a triangle
                        cpoly.set_visible(True)
                        cline.set_visible(False)
                        cpoly.set_xy([p3, p4, p_coupler_pos])

                    cpm.set_data([p_coupler_pos[0]], [p_coupler_pos[1]])
                    return dr, fo, cpoly, cline, cpm
                return init, update
            init, update = create_4bar_anim(sim_data, driver, follower, coupler_poly, coupler_line, coupler_point_marker)
            anim_funcs.append({'init': init, 'update': update, 'frames': len(sim_data)})

        elif mech_type == 'cam-follower':
            sim_data = simulate_cam_motion(**params)
            path = np.array([[0, f['follower_y']] for f in sim_data])

            # Normalize path and get parameters
            normalized_path, norm_params = normalize_path(path.tolist())

            # Calculate cam mechanism geometry
            base_radius = params['base_radius']
            eccentricity = params['eccentricity']
            cam_center = np.array([eccentricity, 0])

            # Calculate bounding box including cam profile
            follower_ys = [f['follower_y'] for f in sim_data]
            min_y, max_y = min(follower_ys), max(follower_ys)

            dataset_entry = {
                "type": "Cam Follower",
                "name": f"Cam {config['name']}",
                "parameters": params,
                "path_coordinates": normalized_path,
                "path_normalization": norm_params,
                "key_points": {
                    "cam_center": cam_center.tolist(),
                    "rotation_center": [0, 0],
                    "follower_path_bounds": {"min_y": min_y, "max_y": max_y},
                    "initial_follower_position": [0, sim_data[0]['follower_y']]
                },
                "skeleton_attachment": {
                    "attachment_point": "follower",
                    "attachment_coordinates": [0, sim_data[0]['follower_y']],
                    "description": "The follower moves vertically and drives skeleton animation"
                },
                "mechanism_layout": {
                    "description": "Cam-follower with eccentric cam rotating about origin",
                    "components": {
                        "cam": {"center_offset": eccentricity, "radius": base_radius, "rotates": True},
                        "follower": {"position": [0, "variable_y"], "motion": "vertical_translation"}
                    },
                    "coordinate_system": {
                        "origin": "cam rotation center",
                        "x_axis": "horizontal right",
                        "y_axis": "vertical up"
                    }
                },
                "visualization_params": {
                    "center": [0, (min_y + max_y) / 2],
                    "scale": max(base_radius + eccentricity, (max_y - min_y) / 2),
                    "bounding_box": {
                        "min": [-base_radius - eccentricity, min_y],
                        "max": [base_radius + eccentricity, max_y]
                    }
                }
            }
            dataset_aggregator.append(dataset_entry)

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
            path = np.array([f['tracking_point'] for f in sim_data]) # Path on driver gear circumference

            # Normalize path and get parameters
            normalized_path, norm_params = normalize_path(path.tolist())

            # Calculate gear mechanism geometry - gears should be touching
            gear1_center = np.array([0, 0])  # Left gear center at origin
            gear2_center = np.array([r1 + r2, 0])   # Right gear center at distance r1+r2

            # Initial position on gear 1 circumference
            initial_gear_point = gear1_center + np.array([r1, 0])

            dataset_entry = {
                "type": "Gear Contact",
                "name": f"Gear {config['name']}",
                "parameters": params,
                "path_coordinates": normalized_path,
                "path_normalization": norm_params,
                "key_points": {
                    "gear1_center": gear1_center.tolist(),
                    "gear2_center": gear2_center.tolist(),
                    "contact_point": [0, 0],  # Contact point between gears
                    "initial_tracking_point": initial_gear_point.tolist()
                },
                "skeleton_attachment": {
                    "attachment_point": "gear1_circumference",
                    "attachment_coordinates": initial_gear_point.tolist(),
                    "description": "A point on gear 1 circumference follows circular path and drives skeleton"
                },
                "mechanism_layout": {
                    "description": "Two meshing gears with gear ratio r1:r2",
                    "components": {
                        "gear1": {"center": gear1_center.tolist(), "radius": r1, "driver": True},
                        "gear2": {"center": gear2_center.tolist(), "radius": r2, "driven": True}
                    },
                    "gear_ratio": r1 / r2,
                    "coordinate_system": {
                        "origin": "midpoint between gear centers",
                        "x_axis": "horizontal right",
                        "gear_separation": r1 + r2
                    }
                },
                "visualization_params": {
                    "center": [(r1 + r2) / 2, 0],  # Center between gears
                    "scale": max(r1, r2),
                    "bounding_box": {
                        "min": [-r1, -max(r1, r2)],
                        "max": [r1 + r2 + r2, max(r1, r2)]
                    }
                }
            }
            dataset_aggregator.append(dataset_entry)

            p1, p2 = gear1_center, gear2_center
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

    # Create the animation
    ani = FuncAnimation(fig, master_update, frames=range(180), init_func=anim_funcs[0]['init'], blit=True, interval=50)
    anim_path = os.path.join(output_dir, f"{title.replace(' ', '_').lower()}.gif")
    ani.save(anim_path, writer='imagemagick', fps=20)
    print(f"Saved animation to {anim_path}")

    plt.close(fig)
    print(f"Processed mechanisms for: {title}")

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

    # --- Save Dataset Safely ---
    dataset_path = os.path.join(os.path.dirname(__file__), "..", "kinematics", "generated_mechanism_paths.json")
    temp_dataset_path = dataset_path + ".tmp"
    os.makedirs(os.path.dirname(dataset_path), exist_ok=True)

    print(f"\nSafely overwriting dataset with {len(all_mechanisms_data)} mechanisms at: {dataset_path}")
    try:
        with open(temp_dataset_path, 'w') as f:
            json.dump(all_mechanisms_data, f, indent=2)
        # Atomic rename to replace the old file with the new one
        os.rename(temp_dataset_path, dataset_path)
        print("✓ Dataset saved successfully.")
    except Exception as e:
        print(f"Error saving dataset: {e}")
    finally:
        # Clean up temp file if it still exists
        if os.path.exists(temp_dataset_path):
            os.remove(temp_dataset_path)

    print("\n✓ Generation complete!")

if __name__ == "__main__":
    main()
