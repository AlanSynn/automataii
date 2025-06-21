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
from matplotlib.animation import FuncAnimation, FFMpegWriter
from typing import List, Dict, Any, Tuple
from scipy.optimize import fsolve
from datetime import datetime
import math

# --- UTILITIES ---

def gcd(a, b):
    return math.gcd(a, b)

def lcm(a, b):
    return abs(a*b) // gcd(a, b) if a != 0 and b != 0 else 0

def normalize_path(path_coords: List[List[float]], target_bounds: Tuple[float, float] = (-1.0, 1.0)) -> Tuple[List[List[float]], Dict]:
    if not path_coords: return [], {}
    coords_array = np.array(path_coords)
    min_vals, max_vals = coords_array.min(axis=0), coords_array.max(axis=0)
    center = (min_vals + max_vals) / 2
    ranges = max_vals - min_vals
    ranges[ranges == 0] = 1
    max_range = np.max(ranges)
    normalized = (coords_array - center) / (max_range / 2)
    norm_params = {"center": center.tolist(), "scale": max_range / 2, "original_bounds": [min_vals.tolist(), max_vals.tolist()]}
    return normalized.tolist(), norm_params

# --- KINEMATIC SIMULATORS ---

def solve_4bar_closure(x, l1, l2, l3, l4, theta2):
    theta3, theta4 = x
    return (l2*np.cos(theta2) + l3*np.cos(theta3) - l4*np.cos(theta4) - l1,
            l2*np.sin(theta2) + l3*np.sin(theta3) - l4*np.sin(theta4))

def simulate_4bar_motion(l1, l2, l3, l4, p_x, p_y, num_steps=180):
    sim_data = []
    last_sol = [np.pi/2, np.pi/2]
    p1, p2 = np.array([0, 0]), np.array([l1, 0])
    for theta2 in np.linspace(0, 2*np.pi, num_steps):
        sol, _, ier, _ = fsolve(solve_4bar_closure, last_sol, args=(l1, l2, l3, l4, theta2), full_output=True)
        if ier == 1:
            last_sol = sol
            theta3, theta4 = sol
            p3 = p1 + np.array([l2*np.cos(theta2), l2*np.sin(theta2)])
            p4 = p2 + np.array([l4*np.cos(theta4), l4*np.sin(theta4)])
            coupler_vec = p4 - p3
            if np.linalg.norm(coupler_vec) > 0:
                coupler_unit = coupler_vec / np.linalg.norm(coupler_vec)
                coupler_normal = np.array([-coupler_unit[1], coupler_unit[0]])
                p_coupler = p3 + p_x * coupler_unit + p_y * coupler_normal
            else:
                p_coupler = p3
            sim_data.append({'p1': p1, 'p2': p2, 'p3': p3, 'p4': p4, 'p_coupler': p_coupler, 'theta2': theta2, 'theta3': theta3, 'theta4': theta4})
    return sim_data

def simulate_cam_motion(base_radius, eccentricity, num_steps=180):
    sim_data = []
    cam_offset = np.array([eccentricity, 0])
    for theta in np.linspace(0, 2*np.pi, num_steps):
        rot = np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]])
        rotated_center = rot @ cam_offset
        follower_y = rotated_center[1] + base_radius
        sim_data.append({'cam_center': rotated_center, 'follower_y': follower_y})
    return sim_data

def simulate_planetary_gear_motion(r_sun, r_planet, arm_length, num_steps_per_rev=180):
    sim_data = []
    sun_center = np.array([0, 0])
    r_sun, r_planet = int(r_sun), int(r_planet)
    num_revolutions = lcm(r_sun, r_planet) / r_sun
    total_steps = int(num_steps_per_rev * num_revolutions)
    for t in np.linspace(0, 2 * np.pi * num_revolutions, total_steps):
        planet_center = sun_center + (r_sun + r_planet) * np.array([np.cos(t), np.sin(t)])
        planet_rotation = -t * (r_sun / r_planet)
        tracking_point = planet_center + arm_length * np.array([np.cos(planet_rotation), np.sin(planet_rotation)])
        sim_data.append({'sun_center': sun_center, 'planet_center': planet_center, 'tracking_point': tracking_point, 'planet_orbital_angle': t, 'planet_rotation_angle': planet_rotation})
    return sim_data, int(total_steps)

def simulate_simple_gear_motion(r1, r2, distance, tracking_radius, num_steps=180):
    """Simulate motion of a simple gear pair with tracking point on driven gear."""
    sim_data = []
    gear1_center = np.array([0, 0])
    gear2_center = np.array([distance, 0])

    # Calculate gear ratio
    gear_ratio = r1 / r2

    for t in np.linspace(0, 2 * np.pi, num_steps):
        # Driving gear rotates at constant speed
        theta1 = t
        # Driven gear rotates based on gear ratio (opposite direction)
        theta2 = -t * gear_ratio

        # Tracking point on driven gear
        tracking_point = gear2_center + tracking_radius * np.array([np.cos(theta2), np.sin(theta2)])

        sim_data.append({
            'gear1_center': gear1_center,
            'gear2_center': gear2_center,
            'gear1_angle': theta1,
            'gear2_angle': theta2,
            'tracking_point': tracking_point
        })

    return sim_data

# --- CONFIGURATION GENERATORS ---

def generate_crank_rocker_configs(num_configs: int, max_dim: float = 100.0) -> List[Dict[str, Any]]:
    configs = []
    attempts = 0
    while len(configs) < num_configs and attempts < 500:
        attempts += 1
        l1, l2, l3, l4 = np.random.uniform(0.3*max_dim, 0.7*max_dim), np.random.uniform(0.1*max_dim, 0.25*max_dim), np.random.uniform(0.5*max_dim, 1.2*max_dim), np.random.uniform(0.5*max_dim, 1.2*max_dim)
        links = {'l1': l1, 'l2': l2, 'l3': l3, 'l4': l4}
        s_link_name = min(links, key=links.get)
        if s_link_name != 'l2': continue
        s, l = links[s_link_name], max(links.values())
        if s + l > sum(links.values()) - s - l: continue
        p_x, p_y = np.random.uniform(l3*0.2, l3*0.8), np.random.uniform(-l3*0.5, l3*0.5)
        configs.append({'type': '4-bar', 'name': f'Crank-Rocker #{len(configs)+1}', 'params': {'l1': l1, 'l2': l2, 'l3': l3, 'l4': l4, 'p_x': p_x, 'p_y': p_y}})
    if len(configs) > 0:
        configs[0]['name'], configs[0]['params']['p_x'], configs[0]['params']['p_y'] = 'Crank-Rocker (Center Coupler)', configs[0]['params']['l3']/2, 0
    print(f"Generated {len(configs)} diverse Crank-Rocker configurations.")
    return configs

def generate_planetary_gear_configs(num_configs: int) -> List[Dict[str, Any]]:
    configs = []
    def find_valid_radii(max_revolutions=4):
        for _ in range(100):
            r_sun, r_planet = np.random.randint(10, 41), np.random.randint(10, 41)
            if r_sun > 0 and 0 < lcm(r_sun, r_planet)/r_sun <= max_revolutions: return r_sun, r_planet
        return 20, 30
    cases = [('Perfect Circle Path', 0), ('Epicycloid (Cusp)', 1), ('Epitrochoid (Loop)', 1.5), ('Epitrochoid (Smooth)', 0.5)]
    for name, arm_factor in cases:
        r_sun, r_planet = find_valid_radii()
        configs.append({'type': 'planetary-gear', 'name': name, 'params': {'r_sun': r_sun, 'r_planet': r_planet, 'arm_length': r_planet * arm_factor}})
    while len(configs) < num_configs:
        r_sun, r_planet = find_valid_radii()
        arm_length = r_planet * np.random.uniform(0.4, 1.6)
        configs.append({'type': 'planetary-gear', 'name': f'Planetary Gear #{len(configs)}', 'params': {'r_sun': r_sun, 'r_planet': r_planet, 'arm_length': arm_length}})
    print(f"Generated {len(configs)} diverse Planetary Gear configurations.")
    return configs

def generate_cam_follower_configs(num_configs: int) -> List[Dict[str, Any]]:
    """Generate configurations for cam-follower mechanisms with different eccentricities."""
    configs = []

    # Add some specific cases
    cases = [
        ('Centered Cam (Simple Harmonic)', 25.0, 0.0),
        ('Small Eccentricity', 25.0, 5.0),
        ('Medium Eccentricity', 25.0, 10.0),
        ('Large Eccentricity', 20.0, 15.0)
    ]

    for name, base_radius, eccentricity in cases:
        configs.append({
            'type': 'cam-follower',
            'name': name,
            'params': {
                'base_radius': base_radius,
                'eccentricity': eccentricity
            }
        })

    # Generate random configs for remaining slots
    while len(configs) < num_configs:
        base_radius = np.random.uniform(15, 35)
        eccentricity = np.random.uniform(0, base_radius * 0.6)

        configs.append({
            'type': 'cam-follower',
            'name': f'Cam-Follower #{len(configs)}',
            'params': {
                'base_radius': base_radius,
                'eccentricity': eccentricity
            }
        })

    print(f"Generated {len(configs)} diverse Cam-Follower configurations.")
    return configs

def generate_simple_gear_configs(num_configs: int) -> List[Dict[str, Any]]:
    """Generate configurations for simple gear pairs with different ratios and tracking points."""
    configs = []

    # Add some specific cases
    cases = [
        ('1:1 Gear Ratio', 20, 20, 0.8),
        ('2:1 Speed Reduction', 30, 15, 0.9),
        ('1:2 Speed Increase', 15, 30, 0.7),
        ('3:1 Speed Reduction', 36, 12, 1.0)
    ]

    for name, r1, r2, track_factor in cases:
        distance = r1 + r2  # Gears touching
        tracking_radius = r2 * track_factor
        configs.append({
            'type': 'simple-gear',
            'name': name,
            'params': {
                'r1': r1,
                'r2': r2,
                'distance': distance,
                'tracking_radius': tracking_radius
            }
        })

    # Generate random configs for remaining slots
    while len(configs) < num_configs:
        r1 = np.random.uniform(15, 40)
        r2 = np.random.uniform(10, 35)
        distance = r1 + r2
        tracking_radius = r2 * np.random.uniform(0.5, 1.2)

        configs.append({
            'type': 'simple-gear',
            'name': f'Simple Gear #{len(configs)}',
            'params': {
                'r1': r1,
                'r2': r2,
                'distance': distance,
                'tracking_radius': tracking_radius
            }
        })

    print(f"Generated {len(configs)} diverse Simple Gear configurations.")
    return configs

# --- VISUALIZATION & DATASET GENERATION ---

def process_mechanisms(configs: List[Dict[str, Any]], title: str, output_dir: str, dataset_aggregator: List):
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
            sim_data = simulate_4bar_motion(**params)
            path = np.array([f['p_coupler'] for f in sim_data])
            normalized_path, norm_params = normalize_path(path.tolist())
            # Create the expected structure with joint_positions
            full_simulation_data = {
                "coupler_path": [d['p_coupler'].tolist() for d in sim_data],
                "link_lengths": {"l1": params['l1'], "l2": params['l2'], "l3": params['l3'], "l4": params['l4']},
                "joint_positions": {
                    "p1_positions": [d['p1'].tolist() for d in sim_data],
                    "p2_positions": [d['p2'].tolist() for d in sim_data],
                    "p3_positions": [d['p3'].tolist() for d in sim_data],
                    "p4_positions": [d['p4'].tolist() for d in sim_data],
                    "coupler_positions": [d['p_coupler'].tolist() for d in sim_data]
                }
            }
            dataset_entry = {
                "type": "4-bar Coupler", "name": f"4-bar {config['name']}", "parameters": params,
                "path_coordinates": normalized_path, "path_normalization": norm_params,
                "full_simulation_data": full_simulation_data
            }
            dataset_aggregator.append(dataset_entry)
            ground_p1, ground_p2 = sim_data[0]['p1'], sim_data[0]['p2']
            ax.plot(path[:,0], path[:,1], '--m', lw=1.5)
            driver, = ax.plot([],[], 'o-', c='orange', lw=5)
            follower, = ax.plot([],[], 'o-', c='gold', lw=5)
            coupler_poly = plt.Polygon([[0,0],[0,0],[0,0]], fc='lightgreen', alpha=0.8, zorder=2, visible=False)
            coupler_line, = ax.plot([],[], '-', c='lightgreen', lw=4, zorder=2, visible=False)
            ax.add_patch(coupler_poly)
            cpm, = ax.plot([],[], 'o', c='red', ms=8, zorder=3)
            def create_4bar_anim(sd, dr, fo, cpoly, cline, cpm):
                def init():
                    padding=5; ax.set_xlim(path[:,0].min()-padding, path[:,0].max()+padding); ax.set_ylim(path[:,1].min()-padding, path[:,1].max()+padding)
                    return dr, fo, cpoly, cline, cpm
                def update(idx):
                    fr = sd[idx]; p1,p3,p2,p4,pc = fr['p1'],fr['p3'],fr['p2'],fr['p4'],fr['p_coupler']
                    dr.set_data([p1[0],p3[0]], [p1[1],p3[1]]); fo.set_data([p2[0],p4[0]], [p2[1],p4[1]])
                    if np.abs(p3[0]*(p4[1]-pc[1]) + p4[0]*(pc[1]-p3[1]) + pc[0]*(p3[1]-p4[1]))/2 < 1e-3:
                        cpoly.set_visible(False); cline.set_visible(True); cline.set_data([p3[0],p4[0]], [p3[1],p4[1]])
                    else:
                        cpoly.set_visible(True); cline.set_visible(False); cpoly.set_xy([p3,p4,pc])
                    cpm.set_data([pc[0]],[pc[1]])
                    return dr,fo,cpoly,cline,cpm
                return init, update
            anim_funcs.append({'init': create_4bar_anim(sim_data, driver, follower, coupler_poly, coupler_line, cpm)[0], 'update': create_4bar_anim(sim_data, driver, follower, coupler_poly, coupler_line, cpm)[1], 'frames': len(sim_data)})

        elif mech_type == 'planetary-gear':
            sim_data, total_frames = simulate_planetary_gear_motion(**params)
            path = np.array([f['tracking_point'] for f in sim_data])
            normalized_path, norm_params = normalize_path(path.tolist())
            # Create structured data for planetary gear
            full_simulation_data = {
                "tracking_path": [d['tracking_point'].tolist() for d in sim_data],
                "gear_params": params,
                "gear_positions": {
                    "sun_centers": [d['sun_center'].tolist() for d in sim_data],
                    "planet_centers": [d['planet_center'].tolist() for d in sim_data],
                    "tracking_points": [d['tracking_point'].tolist() for d in sim_data],
                    "planet_orbital_angles": [d['planet_orbital_angle'] for d in sim_data],
                    "planet_rotation_angles": [d['planet_rotation_angle'] for d in sim_data]
                }
            }
            dataset_entry = {
                "type": "Planetary Gear", "name": config['name'], "parameters": params,
                "path_coordinates": normalized_path, "path_normalization": norm_params,
                "full_simulation_data": full_simulation_data
            }
            dataset_aggregator.append(dataset_entry)
            r_sun, r_planet, arm_length = params['r_sun'], params['r_planet'], params['arm_length']
            sun_patch = plt.Circle(sim_data[0]['sun_center'], r_sun, color='slategray', zorder=1)
            planet_patch = plt.Circle(sim_data[0]['planet_center'], r_planet, color='coral', zorder=1)
            ax.add_patch(sun_patch); ax.add_patch(planet_patch)
            arm, = ax.plot([],[], 'o-', c='gold', lw=2, ms=4, zorder=2)
            path_line, = ax.plot(path[:,0], path[:,1], '--c', lw=1.5, zorder=3)
            tracker, = ax.plot([],[], 'o', c='red', ms=8, zorder=4)
            def create_planetary_anim(sd, pp, arm_l, tr):
                def init():
                    padding=5; max_r = r_sun+r_planet+arm_length; ax.set_xlim(-max_r-padding, max_r+padding); ax.set_ylim(-max_r-padding, max_r+padding)
                    return pp, arm_l, tr
                def update(idx):
                    fr = sd[idx]; pc, tp = fr['planet_center'], fr['tracking_point']
                    pp.set_center(pc); arm_l.set_data([pc[0],tp[0]], [pc[1],tp[1]]); tr.set_data([tp[0]],[tp[1]])
                    return pp, arm_l, tr
                return init, update
            init, update = create_planetary_anim(sim_data, planet_patch, arm, tracker)
            anim_funcs.append({'init': init, 'update': update, 'frames': total_frames})

        elif mech_type == 'cam-follower':
            sim_data = simulate_cam_motion(**params)
            # Extract follower path
            follower_positions = [[0, d['follower_y']] for d in sim_data]
            normalized_path, norm_params = normalize_path(follower_positions)
            # Create structured data for cam-follower
            full_simulation_data = {
                "follower_path": follower_positions,
                "cam_params": params,
                "cam_data": {
                    "cam_centers": [d['cam_center'].tolist() for d in sim_data],
                    "follower_y_positions": [d['follower_y'] for d in sim_data]
                }
            }
            dataset_entry = {
                "type": "Cam-Follower", "name": config['name'], "parameters": params,
                "path_coordinates": normalized_path, "path_normalization": norm_params,
                "full_simulation_data": full_simulation_data
            }
            dataset_aggregator.append(dataset_entry)

            # Visualization setup
            base_radius, eccentricity = params['base_radius'], params['eccentricity']
            cam_circle = plt.Circle([0, 0], base_radius, color='steelblue', alpha=0.7, zorder=1)
            ax.add_patch(cam_circle)
            follower_rect = plt.Rectangle([-5, base_radius], 10, 20, color='coral', zorder=2)
            ax.add_patch(follower_rect)
            cam_center_dot, = ax.plot([], [], 'o', c='darkblue', ms=6, zorder=3)

            def create_cam_anim(sd, cam_circ, foll_rect, cam_dot):
                def init():
                    padding = 10
                    max_y = base_radius + eccentricity + 25
                    ax.set_xlim(-base_radius-eccentricity-padding, base_radius+eccentricity+padding)
                    ax.set_ylim(-base_radius-eccentricity-padding, max_y+padding)
                    return cam_circ, foll_rect, cam_dot
                def update(idx):
                    fr = sd[idx]
                    cam_center, follower_y = fr['cam_center'], fr['follower_y']
                    cam_circ.set_center(cam_center)
                    foll_rect.set_y(follower_y)
                    cam_dot.set_data([cam_center[0]], [cam_center[1]])
                    return cam_circ, foll_rect, cam_dot
                return init, update
            init, update = create_cam_anim(sim_data, cam_circle, follower_rect, cam_center_dot)
            anim_funcs.append({'init': init, 'update': update, 'frames': len(sim_data)})

        elif mech_type == 'simple-gear':
            sim_data = simulate_simple_gear_motion(**params)
            path = np.array([d['tracking_point'] for d in sim_data])
            normalized_path, norm_params = normalize_path(path.tolist())
            # Create structured data for simple gear
            full_simulation_data = {
                "tracking_path": [d['tracking_point'].tolist() for d in sim_data],
                "gear_params": params,
                "gear_data": {
                    "gear1_centers": [d['gear1_center'].tolist() for d in sim_data],
                    "gear2_centers": [d['gear2_center'].tolist() for d in sim_data],
                    "gear1_angles": [d['gear1_angle'] for d in sim_data],
                    "gear2_angles": [d['gear2_angle'] for d in sim_data],
                    "tracking_points": [d['tracking_point'].tolist() for d in sim_data]
                }
            }
            dataset_entry = {
                "type": "Simple Gear", "name": config['name'], "parameters": params,
                "path_coordinates": normalized_path, "path_normalization": norm_params,
                "full_simulation_data": full_simulation_data
            }
            dataset_aggregator.append(dataset_entry)

            # Visualization setup
            r1, r2 = params['r1'], params['r2']
            gear1_circle = plt.Circle(sim_data[0]['gear1_center'], r1, color='darkgreen', alpha=0.7, zorder=1)
            gear2_circle = plt.Circle(sim_data[0]['gear2_center'], r2, color='darkred', alpha=0.7, zorder=1)
            ax.add_patch(gear1_circle)
            ax.add_patch(gear2_circle)

            # Add gear teeth indicators
            gear1_line, = ax.plot([], [], '-', c='darkgreen', lw=3, zorder=2)
            gear2_line, = ax.plot([], [], '-', c='darkred', lw=3, zorder=2)
            tracking_point_marker, = ax.plot([], [], 'o', c='gold', ms=8, zorder=3)
            path_line, = ax.plot(path[:,0], path[:,1], '--b', lw=1.5, alpha=0.5)

            def create_gear_anim(sd, g1_line, g2_line, track_marker):
                def init():
                    padding = 10
                    all_x = [d['tracking_point'][0] for d in sd]
                    all_y = [d['tracking_point'][1] for d in sd]
                    ax.set_xlim(min(all_x)-padding, max(all_x)+padding)
                    ax.set_ylim(min(all_y)-padding, max(all_y)+padding)
                    return g1_line, g2_line, track_marker
                def update(idx):
                    fr = sd[idx]
                    g1_center, g2_center = fr['gear1_center'], fr['gear2_center']
                    theta1, theta2 = fr['gear1_angle'], fr['gear2_angle']
                    tracking_pt = fr['tracking_point']

                    # Update gear rotation indicators
                    g1_end = g1_center + r1 * np.array([np.cos(theta1), np.sin(theta1)])
                    g2_end = g2_center + r2 * np.array([np.cos(theta2), np.sin(theta2)])
                    g1_line.set_data([g1_center[0], g1_end[0]], [g1_center[1], g1_end[1]])
                    g2_line.set_data([g2_center[0], g2_end[0]], [g2_center[1], g2_end[1]])
                    track_marker.set_data([tracking_pt[0]], [tracking_pt[1]])

                    return g1_line, g2_line, track_marker
                return init, update
            init, update = create_gear_anim(sim_data, gear1_line, gear2_line, tracking_point_marker)
            anim_funcs.append({'init': init, 'update': update, 'frames': len(sim_data)})

    total_master_frames = max((f['frames'] for f in anim_funcs), default=0)
    if total_master_frames > 0:
        writer = FFMpegWriter(fps=30)
        ani = FuncAnimation(fig, lambda i: [a for f in anim_funcs for a in f['update'](i % f['frames'])], frames=total_master_frames, init_func=lambda: [a for f in anim_funcs for a in f['init']()], blit=True, interval=33)
        anim_path = os.path.join(output_dir, f"{title.replace(' ', '_').lower()}.mp4")
        ani.save(anim_path, writer=writer)
        print(f"Saved animation to {anim_path}")
    plt.close(fig)
    print(f"Processed mechanisms for: {title}")

def main():
    parser = argparse.ArgumentParser(description="Generate and visualize mechanism datasets.")
    from automataii.utils.paths import get_project_root
    project_root = get_project_root()
    base_dir = project_root / "generated_mechanisms"
    parser.add_argument("--output_dir", type=str, default=str(base_dir / "animations"))
    args = parser.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)
    print("\n=== Mechanism Animation and Dataset Generator ===\n")
    all_mechanisms_data = []

    configs = [
        *generate_crank_rocker_configs(4),
        *generate_cam_follower_configs(4),
        *generate_planetary_gear_configs(4),
        *generate_simple_gear_configs(4)
    ]

    process_mechanisms([c for c in configs if c['type'] == '4-bar'], "4-Bar Crank-Rocker Linkages", args.output_dir, all_mechanisms_data)
    process_mechanisms([c for c in configs if c['type'] == 'cam-follower'], "Cam-Follower Mechanisms", args.output_dir, all_mechanisms_data)
    process_mechanisms([c for c in configs if c['type'] == 'planetary-gear'], "Planetary Gear Trains", args.output_dir, all_mechanisms_data)
    process_mechanisms([c for c in configs if c['type'] == 'simple-gear'], "Simple Gear Pairs", args.output_dir, all_mechanisms_data)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dataset_filename = f"generated_mechanism_paths_{timestamp}.json"
    kinematics_dir = project_root / "src" / "automataii" / "kinematics"
    dataset_path = kinematics_dir / dataset_filename
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"\nCreating new dataset with {len(all_mechanisms_data)} mechanisms at: {dataset_path}")
    try:
        with open(dataset_path, 'w') as f:
            json.dump(all_mechanisms_data, f, indent=2)
        print("✓ New dataset created successfully.")
    except Exception as e:
        print(f"Error creating dataset: {e}")
    print("\n✓ Generation complete!")

if __name__ == "__main__":
    main()
