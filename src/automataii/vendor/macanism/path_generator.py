# path_generator.py
import numpy as np
from scipy.optimize import fsolve
import itertools
import os
import sys
import json
import matplotlib.pyplot as plt

# --- Configuration ---
# All units are in cm. The workspace is assumed to be 1m x 1m (100cm x 100cm).
OUTPUT_DIR = "generated_mechanisms"
IMG_DIR = os.path.join(OUTPUT_DIR, "images")
JSON_PATH = os.path.join(OUTPUT_DIR, "mechanism_paths.json")
REPORT_PATH = "mechanism_generation.md"

# Create output directories
os.makedirs(IMG_DIR, exist_ok=True)

# Parameter space for link lengths, radii, etc.
PARAM_VALUES = [10.0, 20.0, 40.0, 80.0]
GROUND_LINK_VALUES = [20.0, 50.0, 100.0]
GEAR_RATIOS = [-2.0, -1.0, 0.5, 2.0]

N_POINTS = 360
THETA_INPUT_DRIVER = np.linspace(0, 2 * np.pi, N_POINTS, endpoint=False) # Use endpoint=False for better closure check

# Global list to store all generated path data
generated_paths_data = []


# --- Helper & Validation Functions ---

def is_four_bar_crank_rotatable(l1, l2, l3, l4):
    """
    Checks Grashof condition and ensures the input link (l1) is the crank,
    allowing for full 360-degree rotation.
    """
    lengths = [l1, l2, l3, l4]
    s, l = min(lengths), max(lengths)
    # The sum of the other two links
    pq = sum(lengths) - s - l

    # Grashof condition: s + l <= p + q
    if s + l > pq:
        return False

    # To be a crank, the input link must be the shortest link
    if l1 != s:
        return False

    return True

def is_five_bar_geared_rotatable(l1, l2, l3, l4, l5, k):
    """
    Checks if the geared five-bar linkage can assemble and move through a full rotation.
    It checks if the distance between the two moving pivots on the 'virtual' 4-bar
    is valid for all input angles.
    """
    thetas = THETA_INPUT_DRIVER
    # Calculate the squared distance 'd^2' of the virtual link connecting the pivots
    # of l2 and l3 for the entire range of motion of the input links l1 and l4.
    d_squared = (l5 + l4 * np.cos(k * thetas) - l1 * np.cos(thetas))**2 + \
                (l4 * np.sin(k * thetas) - l1 * np.sin(thetas))**2

    # For the links l2, l3 and the virtual link 'd' to form a triangle,
    # the triangle inequality must hold: |l2 - l3| <= d <= l2 + l3
    lower_bound_sq = (l2 - l3)**2
    upper_bound_sq = (l2 + l3)**2

    # Check if d^2 is within the valid range for all thetas
    return np.all((d_squared >= lower_bound_sq) & (d_squared <= upper_bound_sq))

def check_path_continuity(path, max_jump_factor=5.0):
    """Checks for large jumps in the path indicating discontinuity."""
    if len(path) < 3:
        return True
    points = np.array(path)
    distances = np.linalg.norm(np.diff(points, axis=0), axis=1)
    if len(distances) < 2:
        return True

    median_dist = np.median(distances)
    if np.isclose(median_dist, 0): # Path is stationary or has collapsed
        return False

    # A jump is a point where the distance to the next point is much larger
    # than the median distance between points.
    max_allowed_jump = median_dist * max_jump_factor
    # Any single large jump makes the path discontinuous.
    return np.all(distances < max_allowed_jump)

def check_path_closure(path, tolerance=1.0): # Relaxed tolerance for cm scale
    """Checks if a path is closed."""
    if not path or len(path) < 2:
        return False
    start_point = np.array(path[0])
    end_point = np.array(path[-1])
    return np.allclose(start_point, end_point, atol=tolerance)

# --- Loop Equations ---

def four_bar_loop_equations(unknowns, l1, l2, l3, l4, input_theta1):
    theta2, theta3 = unknowns
    eq1 = l1 * np.cos(input_theta1) + l2 * np.cos(theta2) - l3 * np.cos(theta3) - l4
    eq2 = l1 * np.sin(input_theta1) + l2 * np.sin(theta2) - l3 * np.sin(theta3)
    return (eq1, eq2)

def five_bar_geared_loop_equations(unknowns, l1, l2, l3, l4, l5, gear_ratio_k, theta1):
    theta2, theta3, theta5_virtual = unknowns # Using a 3-unknown formulation
    theta4 = gear_ratio_k * theta1
    # Loop 1: O1 -> A -> C -> O2 -> O1
    eq1 = l1 * np.cos(theta1) + l2 * np.cos(theta2) - l3 * np.cos(theta3) - l5
    eq2 = l1 * np.sin(theta1) + l2 * np.sin(theta2) - l3 * np.sin(theta3)
    # This is a 4-bar loop. Let's reformulate for a 5-bar.
    # O1->A, A->B, B->C, C->O2, O2->O1 (where O1, O2 are grounded)
    # L1, L2, L3, L4, L5(ground)
    # A more standard geared five-bar formulation:
    # l1*e^(i*t1) + l2*e^(i*t2) + l3*e^(i*t3) - l4*e^(i*t4) - l5 = 0
    # where t4 = k*t1. Unknowns are t2 and t3.

    eq1_revised = l1 * np.cos(theta1) + l2 * np.cos(unknowns[0]) + l3 * np.cos(unknowns[1]) - l4 * np.cos(theta4) - l5
    eq2_revised = l1 * np.sin(theta1) + l2 * np.sin(unknowns[0]) + l3 * np.sin(unknowns[1]) - l4 * np.sin(theta4)
    return (eq1_revised, eq2_revised)


# --- Path Generation Functions ---

def generate_four_bar_paths():
    print("Generating 4-Bar Linkage Paths...")
    param_combinations = itertools.product(PARAM_VALUES, PARAM_VALUES, PARAM_VALUES, GROUND_LINK_VALUES)

    coupler_points_def = [
        {"name": "Joint B", "lc_ratio": 1.0, "beta_coupler": 0.0},
        {"name": "Coupler Midpoint", "lc_ratio": 0.5, "beta_coupler": 0.0},
        {"name": "Coupler Triangle", "lc_ratio": 0.75, "beta_coupler": np.pi / 3},
    ]

    for l1, l2, l3, l4 in param_combinations:
        if not is_four_bar_crank_rotatable(l1, l2, l3, l4):
            continue

        for cp_def in coupler_points_def:
            path_coords = []
            current_solution_angles = (np.pi / 2, np.pi / 2)

            for t1_input in THETA_INPUT_DRIVER:
                try:
                    solved_angles, _, ier, _ = fsolve(four_bar_loop_equations, current_solution_angles, args=(l1, l2, l3, l4, t1_input), full_output=True)
                    if ier != 1: # Solver failed
                        path_coords = [] # Invalidate path
                        break

                    theta2_calc, _ = solved_angles
                    current_solution_angles = solved_angles

                    Ax = l1 * np.cos(t1_input)
                    Ay = l1 * np.sin(t1_input)

                    lc = l2 * cp_def["lc_ratio"]
                    coupler_point_angle = theta2_calc + cp_def["beta_coupler"]
                    Px = Ax + lc * np.cos(coupler_point_angle)
                    Py = Ay + lc * np.sin(coupler_point_angle)
                    path_coords.append((Px, Py))
                except Exception:
                    path_coords = []
                    break

            if path_coords and check_path_continuity(path_coords):
                params = {"L1": l1, "L2": l2, "L3": l3, "L4_ground": l4, "trace_point": cp_def['name']}
                generated_paths_data.append(("4-Bar Linkage", params, path_coords))

def generate_five_bar_geared_paths():
    print("Generating Geared 5-Bar Linkage Paths...")
    param_combinations = itertools.product(PARAM_VALUES, PARAM_VALUES, PARAM_VALUES, PARAM_VALUES, GROUND_LINK_VALUES, GEAR_RATIOS)

    for l1, l2, l3, l4, l5, k in param_combinations:
        if not is_five_bar_geared_rotatable(l1, l2, l3, l4, l5, k):
            continue

        path_coords = []
        current_solution_angles = (np.pi, np.pi) # Initial guess for theta2, theta3

        for t1_input in THETA_INPUT_DRIVER:
            try:
                args = (l1, l2, l3, l4, l5, k, t1_input)
                solved_angles, _, ier, _ = fsolve(five_bar_geared_loop_equations, current_solution_angles, args=args, full_output=True)

                if ier != 1:
                    path_coords = []
                    break

                theta2_calc, theta3_calc = solved_angles
                current_solution_angles = solved_angles

                # Path of joint C (between L2 and L3)
                Cx = l1 * np.cos(t1_input) + l2 * np.cos(theta2_calc)
                Cy = l1 * np.sin(t1_input) + l2 * np.sin(theta2_calc)
                path_coords.append((Cx, Cy))
            except Exception:
                path_coords = []
                break

        if path_coords and check_path_continuity(path_coords):
            params = {"L1": l1, "L2": l2, "L3": l3, "L4": l4, "L5_ground": l5, "gear_ratio": k}
            generated_paths_data.append(("Geared 5-Bar Linkage", params, path_coords))

def generate_epicycloid_gear_paths():
    print("Generating Epicycloid Gear Paths...")
    param_combinations = itertools.product(PARAM_VALUES, PARAM_VALUES, [0.5, 1.0, 1.5]) # r_sun, r_planet, arm_ratio

    for r_sun, r_planet, arm_ratio in param_combinations:
        d = r_planet * arm_ratio # distance of tracing point from planet center

        # Epicycloid
        path_epi = []
        for phi in THETA_INPUT_DRIVER:
            x = (r_sun + r_planet) * np.cos(phi) - d * np.cos(((r_sun + r_planet) / r_planet) * phi)
            y = (r_sun + r_planet) * np.sin(phi) - d * np.sin(((r_sun + r_planet) / r_planet) * phi)
            path_epi.append((x, y))
        params_epi = {"sun_radius": r_sun, "planet_radius": r_planet, "trace_arm": d, "type": "Epicycloid"}
        if check_path_continuity(path_epi):
            generated_paths_data.append(("Planetary Gear", params_epi, path_epi))

        # Hypocycloid
        if r_sun > r_planet:
            path_hypo = []
            for phi in THETA_INPUT_DRIVER:
                x = (r_sun - r_planet) * np.cos(phi) + d * np.cos(((r_sun - r_planet) / r_planet) * phi)
                y = (r_sun - r_planet) * np.sin(phi) - d * np.sin(((r_sun - r_planet) / r_planet) * phi)
                path_hypo.append((x,y))
            params_hypo = {"sun_radius": r_sun, "planet_radius": r_planet, "trace_arm": d, "type": "Hypocycloid"}
            if check_path_continuity(path_hypo):
                generated_paths_data.append(("Planetary Gear", params_hypo, path_hypo))

def generate_cam_follower_paths():
    print("Generating CAM Follower Paths...")
    param_combinations = itertools.product(PARAM_VALUES, PARAM_VALUES) # base_radius, rise_height

    for base_radius, rise_height in param_combinations:
        path_coords = []
        # Simple Rise-Fall Cycloidal motion over one revolution
        for theta in THETA_INPUT_DRIVER:
            if theta <= np.pi: # Rise
                s = rise_height * ((theta/np.pi) - (1/(2*np.pi)) * np.sin(2 * theta))
            else: # Fall
                s = rise_height * (1 - ((theta-np.pi)/np.pi - (1/(2*np.pi)) * np.sin(2 * (theta-np.pi))))

            # Path of translating follower in polar coordinates (r, theta) -> (x, y)
            r = base_radius + s
            path_coords.append((r * np.cos(theta), r * np.sin(theta)))

        params = {"base_radius": base_radius, "rise_height": rise_height, "profile": "Cycloidal"}
        if check_path_continuity(path_coords):
            generated_paths_data.append(("CAM Follower", params, path_coords))

def run_path_generation():
    generate_four_bar_paths()
    generate_five_bar_geared_paths()
    generate_epicycloid_gear_paths()
    generate_cam_follower_paths()

    print(f"\n--- Generated {len(generated_paths_data)} kinematically valid paths ---")

    paths_to_save = []
    for i, (m_type, params, path) in enumerate(generated_paths_data):
        serializable_path = [tuple(float(coord) for coord in p) for p in path] if path else []
        if not serializable_path: continue

        paths_to_save.append({
            "id": i,
            "type": m_type,
            "parameters": params,
            "is_closed": check_path_closure(serializable_path),
            "path_coordinates": serializable_path,
        })

    with open(JSON_PATH, "w") as f:
        json.dump(paths_to_save, f, indent=2)
    print(f"\nAll generated paths saved to {JSON_PATH}")
    return paths_to_save

def export_to_markdown(data, num_examples=5):
    print("Generating markdown report...")

    with open(REPORT_PATH, "w") as f:
        f.write("# Mechanism Path Generation Report (Validated)\n\n")
        f.write("This report summarizes kinematically validated mechanism paths.\n\n")

        paths_by_type = {}
        for item in data:
            paths_by_type.setdefault(item['type'], []).append(item)

        for m_type, paths in paths_by_type.items():
            f.write(f"## {m_type}\n\n")
            f.write(f"Found {len(paths)} valid paths. Showing up to {num_examples} examples.\n\n")

            examples = [p for p in paths if p['is_closed']][:num_examples]
            if len(examples) < num_examples:
                examples.extend([p for p in paths if not p['is_closed']][:num_examples - len(examples)])

            for ex in examples:
                path_coords = ex["path_coordinates"]

                fig, ax = plt.subplots(figsize=(6, 6))
                x_coords, y_coords = zip(*path_coords)
                ax.plot(x_coords, y_coords, '-')
                ax.set_title(f"{m_type} - ID: {ex['id']}")
                ax.set_xlabel("X (cm)")
                ax.set_ylabel("Y (cm)")
                ax.grid(True)
                ax.set_aspect('equal', adjustable='box')

                img_filename = f"path_{ex['id']}.png"
                img_path = os.path.join(IMG_DIR, img_filename)
                plt.savefig(img_path)
                plt.close(fig)

                f.write(f"### Path ID: {ex['id']}\n")
                f.write(f"**Closed Path:** {'Yes' if ex['is_closed'] else 'No'}\n\n")
                f.write("**Parameters:**\n```json\n")
                f.write(json.dumps(ex["parameters"], indent=2))
                f.write("\n```\n\n")

                relative_img_path = os.path.join(os.path.basename(OUTPUT_DIR), "images", img_filename)
                f.write(f"![Path Plot {ex['id']}]({relative_img_path})\n\n---\n\n")

    print(f"Markdown report saved to {REPORT_PATH}")


if __name__ == "__main__":
    print("Starting kinematically validated path generation...")
    final_data = run_path_generation()
    if final_data:
        export_to_markdown(final_data)
    else:
        print("No valid paths were generated with the current parameters.")
    print("All tasks finished.")
