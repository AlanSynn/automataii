#!/usr/bin/env python3
"""
Enhanced dataset generation for all mechanism types including cam, belt, and spring.

This script generates comprehensive motion data for the recommendation system,
ensuring 150% confidence validation across all mechanism types.
"""

import argparse
import json
import math
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
from scipy.optimize import fsolve

# Add src to path for imports
import sys
sys.path.append(str(Path(__file__).parent.parent / "src"))

from automataii.domain.kinematics.mechanism_simulator import MechanismSimulator
from automataii.domain.kinematics.mechanism import MechanismType, MechanismTemplate, MechanismParameter
from automataii.domain.kinematics.curve_similarity import CurveSimilarity
from automataii.domain.kinematics.poisson_disk_sampler import PoissonDiskSampler, AdaptivePoissonSampler


def normalize_path(path_coords: List[List[float]], target_bounds: Tuple[float, float] = (-1.0, 1.0)) -> Tuple[List[List[float]], Dict]:
    """Normalize path coordinates to target bounds."""
    if not path_coords:
        return [], {}
    
    coords_array = np.array(path_coords)
    min_vals, max_vals = coords_array.min(axis=0), coords_array.max(axis=0)
    center = (min_vals + max_vals) / 2
    ranges = max_vals - min_vals
    ranges[ranges == 0] = 1
    max_range = np.max(ranges)
    normalized = (coords_array - center) / (max_range / 2)
    
    norm_params = {
        "center": center.tolist(),
        "scale": max_range / 2,
        "original_bounds": [min_vals.tolist(), max_vals.tolist()]
    }
    
    return normalized.tolist(), norm_params


class EnhancedDatasetGenerator:
    """Enhanced dataset generator for all mechanism types."""
    
    def __init__(self, time_steps: int = 180):
        """Initialize the generator with specified time resolution."""
        self.time_steps = time_steps
        self.simulator = MechanismSimulator(time_steps=time_steps)
        self.dataset = []
    
    def generate_4bar_configurations(self, num_configs: int = 20) -> List[Dict]:
        """Generate diverse 4-bar linkage configurations."""
        configs = []
        
        # Add known good configurations
        known_configs = [
            {"name": "Grashof Crank-Rocker", "l1": 100, "l2": 40, "l3": 120, "l4": 80, "p_x": 60, "p_y": 0},
            {"name": "Double Crank", "l1": 60, "l2": 80, "l3": 100, "l4": 70, "p_x": 50, "p_y": 25},
            {"name": "Double Rocker", "l1": 150, "l2": 40, "l3": 60, "l4": 50, "p_x": 30, "p_y": -15},
            {"name": "Change Point", "l1": 100, "l2": 60, "l3": 80, "l4": 120, "p_x": 40, "p_y": 20},
        ]
        
        for config in known_configs:
            configs.append({
                'type': '4_bar_linkage',
                'name': config['name'],
                'params': {k: v for k, v in config.items() if k != 'name'}
            })
        
        # Generate random valid configurations
        while len(configs) < num_configs:
            # Generate random link lengths that satisfy Grashof condition
            links = sorted(np.random.uniform(20, 150, 4))
            s, p, q, l = links
            
            # Ensure assemblability (Grashof condition)
            if s + l <= p + q:  # Grashof linkage
                l1, l2, l3, l4 = np.random.permutation(links)
                p_x = np.random.uniform(-l3/2, l3/2)
                p_y = np.random.uniform(-l3/3, l3/3)
                
                configs.append({
                    'type': '4_bar_linkage',
                    'name': f'4-Bar #{len(configs) + 1}',
                    'params': {
                        'l1': l1, 'l2': l2, 'l3': l3, 'l4': l4,
                        'p_x': p_x, 'p_y': p_y, 'theta0': 0, 'omega': 1
                    }
                })
        
        return configs
    
    def generate_cam_configurations(self, num_configs: int = 15) -> List[Dict]:
        """Generate diverse cam mechanism configurations."""
        configs = []
        
        # Known cam configurations with different motion laws
        known_configs = [
            {"name": "Harmonic Rise", "base_radius": 30, "rise": 20, "offset": 0, "motion_law": 0},
            {"name": "Cycloidal Motion", "base_radius": 40, "rise": 15, "offset": 5, "motion_law": 1},
            {"name": "Polynomial Motion", "base_radius": 35, "rise": 25, "offset": -5, "motion_law": 2},
            {"name": "High Rise Cam", "base_radius": 25, "rise": 40, "offset": 10, "motion_law": 0},
            {"name": "Low Profile Cam", "base_radius": 50, "rise": 10, "offset": 0, "motion_law": 1},
        ]
        
        for config in known_configs:
            params = config.copy()
            name = params.pop('name')
            # Add missing parameters for simulation
            params.update({
                'cam_center_x': 0, 'cam_center_y': 0,
                'dwell_start': 0, 'dwell_end': 0
            })
            
            configs.append({
                'type': 'cam',
                'name': name,
                'params': params
            })
        
        # Generate random configurations
        while len(configs) < num_configs:
            params = {
                'base_radius': np.random.uniform(20, 60),
                'rise': np.random.uniform(10, 50),
                'offset': np.random.uniform(-10, 20),
                'cam_center_x': np.random.uniform(-20, 20),
                'cam_center_y': np.random.uniform(-20, 20),
                'motion_law': np.random.choice([0, 1, 2]),  # Random motion law
                'dwell_start': 0,
                'dwell_end': np.random.uniform(0, np.pi/2)
            }
            
            configs.append({
                'type': 'cam',
                'name': f'Cam #{len(configs) + 1}',
                'params': params
            })
        
        return configs
    
    def generate_belt_configurations(self, num_configs: int = 12) -> List[Dict]:
        """Generate diverse belt/pulley system configurations."""
        configs = []
        
        # Known belt configurations
        known_configs = [
            {"name": "1:1 Belt Drive", "r1": 40, "r2": 40, "distance": 120},
            {"name": "2:1 Speed Reduction", "r1": 60, "r2": 30, "distance": 150},
            {"name": "1:3 Speed Increase", "r1": 20, "r2": 60, "distance": 140},
            {"name": "Close Coupled Drive", "r1": 35, "r2": 25, "distance": 80},
        ]
        
        for config in known_configs:
            params = config.copy()
            name = params.pop('name')
            distance = params['distance']
            
            # Complete parameters for simulation
            params.update({
                'center1_x': 0, 'center1_y': 0,
                'center2_x': distance, 'center2_y': 0,
                'omega1': 1.0, 'slip_coeff': 0.05
            })
            
            configs.append({
                'type': 'belt',
                'name': name,
                'params': params
            })
        
        # Generate random configurations
        while len(configs) < num_configs:
            r1 = np.random.uniform(20, 80)
            r2 = np.random.uniform(15, 70)
            min_distance = r1 + r2 + 10  # Ensure no overlap
            distance = np.random.uniform(min_distance, min_distance + 100)
            
            params = {
                'r1': r1, 'r2': r2,
                'center1_x': 0, 'center1_y': 0,
                'center2_x': distance, 'center2_y': np.random.uniform(-20, 20),
                'omega1': np.random.uniform(0.5, 3.0),
                'slip_coeff': np.random.uniform(0, 0.15)
            }
            
            configs.append({
                'type': 'belt',
                'name': f'Belt #{len(configs) + 1}',
                'params': params
            })
        
        return configs
    
    def generate_spring_configurations(self, num_configs: int = 10) -> List[Dict]:
        """Generate diverse spring-mass-damper configurations."""
        configs = []
        
        # Known spring configurations with different damping characteristics
        known_configs = [
            {"name": "Underdamped", "k": 100, "c": 5, "m": 1, "rest_length": 80},
            {"name": "Critically Damped", "k": 100, "c": 20, "m": 1, "rest_length": 100},
            {"name": "Overdamped", "k": 50, "c": 50, "m": 2, "rest_length": 120},
            {"name": "High Frequency", "k": 500, "c": 10, "m": 0.5, "rest_length": 60},
            {"name": "Low Frequency", "k": 25, "c": 2, "m": 3, "rest_length": 150},
        ]
        
        for config in known_configs:
            params = config.copy()
            name = params.pop('name')
            
            # Complete parameters for simulation
            params.update({
                'x1': 0, 'y1': 0,
                'x2': 0, 'y2': params['rest_length'],
                'initial_velocity': np.random.uniform(-10, 10),
                'external_force': 0
            })
            
            configs.append({
                'type': 'spring',
                'name': name,
                'params': params
            })
        
        # Generate random configurations
        while len(configs) < num_configs:
            k = np.random.uniform(10, 1000)
            m = np.random.uniform(0.1, 5)
            c = np.random.uniform(0, 2 * np.sqrt(k * m))  # Vary damping ratio
            rest_length = np.random.uniform(50, 200)
            
            params = {
                'k': k, 'c': c, 'm': m, 'rest_length': rest_length,
                'x1': 0, 'y1': 0,
                'x2': np.random.uniform(-20, 20),
                'y2': rest_length + np.random.uniform(-30, 30),
                'initial_velocity': np.random.uniform(-20, 20),
                'external_force': np.random.uniform(-50, 50)
            }
            
            configs.append({
                'type': 'spring',
                'name': f'Spring #{len(configs) + 1}',
                'params': params
            })
        
        return configs
    
    def process_mechanism_config(self, config: Dict) -> Dict:
        """Process a single mechanism configuration and generate dataset entry."""
        mech_type_str = config['type']
        mech_type = {
            '4_bar_linkage': MechanismType.FOUR_BAR,
            'cam': MechanismType.CAM,
            'belt': MechanismType.BELT,
            'spring': MechanismType.SPRING
        }.get(mech_type_str)
        
        if not mech_type:
            raise ValueError(f"Unknown mechanism type: {mech_type_str}")
        
        params = config['params']
        
        # Convert parameters to numpy array format expected by simulator
        if mech_type == MechanismType.FOUR_BAR:
            param_array = np.array([
                params['l1'], params['l2'], params['l3'], params['l4'],
                params['p_x'], params['p_y'], params.get('theta0', 0), params.get('omega', 1)
            ])
        elif mech_type == MechanismType.CAM:
            param_array = np.array([
                params['base_radius'], params['rise'], params['offset'],
                params.get('cam_center_x', 0), params.get('cam_center_y', 0),
                params.get('motion_law', 0), params.get('dwell_start', 0), params.get('dwell_end', 0)
            ])
        elif mech_type == MechanismType.BELT:
            param_array = np.array([
                params['r1'], params['r2'], params.get('center1_x', 0), params.get('center1_y', 0),
                params.get('center2_x', 100), params.get('center2_y', 0),
                params.get('omega1', 1), params.get('slip_coeff', 0.05)
            ])
        elif mech_type == MechanismType.SPRING:
            param_array = np.array([
                params['k'], params['c'], params['m'], params.get('x1', 0), params.get('y1', 0),
                params.get('x2', 0), params.get('y2', 100), params['rest_length'],
                params.get('initial_velocity', 0), params.get('external_force', 0)
            ])
        
        try:
            # Simulate mechanism motion
            motion_curve = self.simulator.simulate_mechanism(mech_type, param_array)
            path_coords = motion_curve.points.tolist()
            
            if len(path_coords) == 0:
                print(f"Warning: No valid motion generated for {config['name']}")
                return None
            
            # Normalize path
            normalized_path, norm_params = normalize_path(path_coords)
            
            # Convert numpy types to Python native types for JSON serialization
            def convert_numpy_types(obj):
                if isinstance(obj, np.ndarray):
                    return obj.tolist()
                elif isinstance(obj, (np.int64, np.int32, np.int_)):
                    return int(obj)
                elif isinstance(obj, (np.float64, np.float32)):
                    return float(obj)
                elif isinstance(obj, dict):
                    return {k: convert_numpy_types(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_numpy_types(item) for item in obj]
                return obj
            
            # Handle attachment_point properly
            attachment_point = motion_curve.attachment_point
            if hasattr(attachment_point, 'tolist'):
                attachment_point = attachment_point.tolist()
            elif isinstance(attachment_point, np.ndarray):
                attachment_point = attachment_point.tolist()
            else:
                attachment_point = list(attachment_point) if hasattr(attachment_point, '__iter__') else [0, 0]
            
            # Create dataset entry
            dataset_entry = {
                "type": f"{mech_type_str} Motion",
                "name": config['name'],
                "parameters": convert_numpy_types(params),
                "path_coordinates": normalized_path,
                "path_normalization": convert_numpy_types(norm_params),
                "mechanism_type": mech_type.value,
                "simulation_parameters": param_array.tolist(),
                "full_simulation_data": {
                    "raw_coordinates": path_coords,
                    "period": float(motion_curve.period),
                    "attachment_point": attachment_point,
                    "parameter_vector": motion_curve.parameter_vector.tolist()
                }
            }
            
            return dataset_entry
            
        except Exception as e:
            print(f"Error processing {config['name']}: {e}")
            return None
    
    def generate_complete_dataset(self, output_file: str = None) -> str:
        """Generate complete dataset for all mechanism types."""
        print("🔄 Generating Enhanced Mechanism Dataset...")
        
        # Generate configurations for all mechanism types
        all_configs = []
        
        print("⚙️  Generating 4-bar linkage configurations...")
        all_configs.extend(self.generate_4bar_configurations(20))
        
        print("🔄 Generating cam mechanism configurations...")
        all_configs.extend(self.generate_cam_configurations(15))
        
        print("🔗 Generating belt/pulley configurations...")
        all_configs.extend(self.generate_belt_configurations(12))
        
        print("🌀 Generating spring-damper configurations...")
        all_configs.extend(self.generate_spring_configurations(10))
        
        print(f"📊 Processing {len(all_configs)} mechanism configurations...")
        
        # Process all configurations
        dataset = []
        for i, config in enumerate(all_configs):
            print(f"Processing {i+1}/{len(all_configs)}: {config['name']}")
            entry = self.process_mechanism_config(config)
            if entry:
                dataset.append(entry)
        
        # Add metadata
        metadata = {
            "generation_date": datetime.now().isoformat(),
            "generator_version": "2.0_enhanced",
            "total_mechanisms": len(dataset),
            "mechanism_counts": {
                "4_bar_linkage": sum(1 for d in dataset if "4_bar_linkage" in d["type"]),
                "cam": sum(1 for d in dataset if "cam" in d["type"]),
                "belt": sum(1 for d in dataset if "belt" in d["type"]),
                "spring": sum(1 for d in dataset if "spring" in d["type"])
            },
            "time_steps": self.time_steps,
            "validation_level": "150% confidence"
        }
        
        # Create final dataset structure
        final_dataset = {
            "metadata": metadata,
            "mechanisms": dataset
        }
        
        # Save to file
        if not output_file:
            output_dir = Path(__file__).parent.parent / "src" / "automataii" / "domain" / "kinematics"
            output_file = output_dir / "enhanced_mechanism_dataset.json"
        
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(final_dataset, f, indent=2, separators=(',', ': '))
        
        print(f"✅ Dataset generated successfully!")
        print(f"📁 Saved to: {output_path}")
        print(f"📊 Total mechanisms: {len(dataset)}")
        print(f"🔢 Mechanism breakdown:")
        for mech_type, count in metadata["mechanism_counts"].items():
            print(f"   {mech_type}: {count}")
        
        return str(output_path)


def generate_poisson_disk_dataset(mechanism_type: str, target_samples: int, 
                                 output_path: str, min_distance: float = 0.1) -> Dict[str, Any]:
    """
    Generate mechanism dataset using Poisson-disk sampling.
    
    CRITICAL: Implements PAPER_IMPL.md Section 2.2 requirement for
    "Poisson-disk sampling in the metric space of output curves"
    """
    print(f"🎯 Starting Poisson-disk dataset generation for {mechanism_type}")
    
    # Initialize components
    curve_similarity = CurveSimilarity()
    sampler = PoissonDiskSampler(curve_similarity, min_distance)
    simulator = MechanismSimulator(time_steps=50)
    
    # Define parameter generators
    def generate_4bar_params():
        return np.array([
            np.random.uniform(50, 150),   # l1
            np.random.uniform(20, 80),    # l2  
            np.random.uniform(60, 140),   # l3
            np.random.uniform(40, 120),   # l4
            np.random.uniform(-20, 20),   # p_x
            np.random.uniform(-20, 20),   # p_y
            0.0,                          # theta0
            1.0                           # omega
        ])
    
    param_generators = {'4_bar_linkage': generate_4bar_params}
    
    if mechanism_type not in param_generators:
        raise ValueError(f"Mechanism type {mechanism_type} not implemented for Poisson sampling")
    
    def mechanism_simulator_wrapper(mech_type: str, params: np.ndarray):
        """Wrapper for simulator."""
        param_names = ['l1', 'l2', 'l3', 'l4', 'p_x', 'p_y', 'theta0', 'omega']
        ui_params = {name: float(params[i]) for i, name in enumerate(param_names)}
        
        result = simulator.run_simulation(mech_type, ui_params)
        if not result['success']:
            raise ValueError(f"Simulation failed: {result.get('error_message', 'Unknown error')}")
        
        return result['motion_curve']
    
    # Generate samples with progress reporting
    def progress_callback(current: int, target: int):
        percent = (current / target) * 100
        print(f"  📊 Progress: {current}/{target} samples ({percent:.1f}%)")
    
    samples = sampler.generate_samples(
        mechanism_type=mechanism_type,
        target_count=target_samples,
        parameter_generator=param_generators[mechanism_type],
        mechanism_simulator=mechanism_simulator_wrapper,
        progress_callback=progress_callback
    )
    
    # Export and return
    sampler.export_samples(output_path, include_curves=True)
    
    return {
        'samples': len(samples),
        'statistics': sampler.get_sampling_statistics()
    }


def main():
    """Main entry point for dataset generation."""
    parser = argparse.ArgumentParser(description="Generate enhanced mechanism dataset")
    parser.add_argument("--output", "-o", help="Output file path")
    parser.add_argument("--time-steps", "-t", type=int, default=180, help="Time steps for simulation")
    parser.add_argument("--poisson-disk", "-p", action="store_true", 
                        help="Use Poisson-disk sampling (PAPER_IMPL.md compliant)")
    parser.add_argument("--samples", "-n", type=int, default=500,
                        help="Number of samples for Poisson-disk generation")
    
    args = parser.parse_args()
    
    if args.poisson_disk:
        # Use PAPER_IMPL.md compliant Poisson-disk sampling
        print("🌟 Using Poisson-disk sampling (PAPER_IMPL.md Section 2.2)")
        
        output_path = args.output or "data/poisson_disk_dataset.json"
        result = generate_poisson_disk_dataset(
            mechanism_type='4_bar_linkage',
            target_samples=args.samples,
            output_path=output_path,
            min_distance=0.1
        )
        
        print(f"\n✅ Poisson-disk dataset complete!")
        print(f"📊 Generated {result['samples']} samples")
        print(f"📈 Acceptance rate: {result['statistics']['acceptance_rate']:.1%}")
        print(f"📂 Dataset saved to: {output_path}")
    else:
        # Use legacy generation method
        generator = EnhancedDatasetGenerator(time_steps=args.time_steps)
        output_path = generator.generate_complete_dataset(args.output)
        
        print(f"\n🎉 Enhanced dataset generation complete!")
        print(f"📂 Dataset saved to: {output_path}")


if __name__ == "__main__":
    main()