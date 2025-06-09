"""Solver for mechanism kinematic analysis."""

import numpy as np
from scipy.optimize import fsolve


class MechanismSolver:
    """Solver for mechanism position, velocity, and acceleration analysis."""

    def __init__(self, mechanism):
        """
        Initialize the solver.

        Parameters
        ----------
        mechanism : Mechanism
            The mechanism instance to solve.
        """
        self.mechanism = mechanism

    def calculate(self):
        """Solve for a single point in time."""
        mechanism = self.mechanism
        
        # Get input position
        input_pos = (
            mechanism.pos[0]
            if isinstance(mechanism.pos, (list, np.ndarray)) and len(mechanism.pos) > 0
            else mechanism.pos
        )
        
        # Set input vector position
        (
            mechanism.vectors[0](*input_pos)
            if isinstance(input_pos, (np.ndarray, tuple, list))
            else mechanism.vectors[0](input_pos)
        )
        
        # Fix positions
        mechanism._fix_position()
        
        # Solve position loop equations
        s_pos = fsolve(mechanism.loops, mechanism.guess[0], args=(0,))
        
        # Update vector attributes from solved unknowns
        self._update_vector_attributes(s_pos, "position")
        
        # Recalculate positions with solved values
        mechanism._fix_position()
        
        # Solve velocity if provided
        if mechanism.vel is not None:
            input_vel = (
                mechanism.vel[0]
                if isinstance(mechanism.vel, (list, np.ndarray)) and len(mechanism.vel) > 0
                else mechanism.vel
            )
            
            # Switch to velocity analysis
            for v_ in mechanism.vectors:
                v_.get = v_.vel.get
            
            (
                mechanism.vectors[0](*input_vel)
                if isinstance(input_vel, (np.ndarray, tuple, list))
                else mechanism.vectors[0](input_vel)
            )
            mechanism._fix_velocity()
        
        # Solve acceleration if provided
        if mechanism.acc is not None:
            input_acc = (
                mechanism.acc[0]
                if isinstance(mechanism.acc, (list, np.ndarray)) and len(mechanism.acc) > 0
                else mechanism.acc
            )
            
            # Switch to acceleration analysis
            for v_ in mechanism.vectors:
                v_.get = v_.acc.get
            
            (
                mechanism.vectors[0](*input_acc)
                if isinstance(input_acc, (np.ndarray, tuple, list))
                else mechanism.vectors[0](input_acc)
            )
            mechanism._fix_acceleration()

    def iterate(self):
        """Solve for multiple time steps."""
        mechanism = self.mechanism
        
        assert mechanism.is_array, "The input is not an array. Call calculate() instead."
        
        # Use local variables for guesses
        current_pos_guess = mechanism.guess[0]
        current_vel_guess = (
            mechanism.guess[1] if len(mechanism.guess) > 1 and mechanism.vel is not None else None
        )
        current_acc_guess = (
            mechanism.guess[2] if len(mechanism.guess) > 2 and mechanism.acc is not None else None
        )

        for i in range(mechanism.pos.shape[0]):
            # Position analysis
            for v in mechanism.vectors:
                v.get = v.pos.get

            current_pos_input = mechanism.pos[i]
            (
                mechanism.vectors[0](*current_pos_input)
                if isinstance(current_pos_input, (np.ndarray, tuple, list))
                else mechanism.vectors[0](current_pos_input)
            )
            mechanism._fix_position()
            
            # Solve position
            s_pos = fsolve(mechanism.loops, current_pos_guess, args=(i,))
            current_pos_guess = s_pos  # Update for next iteration
            
            # Update vector attributes
            self._update_vector_attributes(s_pos, "position", i)
            mechanism._fix_position()
            
            # Store position data
            for v in mechanism.vectors:
                v._set_position_data(i)
            for j in mechanism.joints:
                j._set_position_data(i)

            # Velocity analysis
            if mechanism.vel is not None and current_vel_guess is not None:
                # Update velocity context
                for v_ in mechanism.vectors:
                    v_._update_velocity()
                
                # Switch to velocity analysis
                for v in mechanism.vectors:
                    v.get = v.vel.get
                
                current_vel_input = mechanism.vel[i]
                (
                    mechanism.vectors[0](*current_vel_input)
                    if isinstance(current_vel_input, (np.ndarray, tuple, list))
                    else mechanism.vectors[0](current_vel_input)
                )
                mechanism._fix_velocity()
                
                # Store velocity data
                for joint in mechanism.joints:
                    joint._set_velocity_data(i)

            # Acceleration analysis
            if mechanism.acc is not None and current_acc_guess is not None:
                assert mechanism.vel is not None, (
                    "vel input not defined, but necessary to solve for accelerations."
                )
                
                # Update acceleration context
                for v_ in mechanism.vectors:
                    v_._update_acceleration()
                
                # Switch to acceleration analysis
                for v in mechanism.vectors:
                    v.get = v.acc.get
                
                current_acc_input = mechanism.acc[i]
                (
                    mechanism.vectors[0](*current_acc_input)
                    if isinstance(current_acc_input, (np.ndarray, tuple, list))
                    else mechanism.vectors[0](current_acc_input)
                )
                mechanism._fix_acceleration()
                
                # Store acceleration data
                for joint in mechanism.joints:
                    joint._set_acceleration_data(i)

            mechanism.clear_joints()

    def _update_vector_attributes(self, solved_values, analysis_type, index=None):
        """Update vector attributes from solved values."""
        mechanism = self.mechanism
        
        if mechanism.unknown_map:
            if len(solved_values) != len(mechanism.unknown_map):
                raise ValueError(
                    f"Mismatch between length of solved {analysis_type} unknowns "
                    f"({len(solved_values)}) and unknown_map ({len(mechanism.unknown_map)})"
                )
            
            for idx, (vector_obj, dof_name) in enumerate(mechanism.unknown_map):
                solved_value = solved_values[idx]
                
                if analysis_type == "position":
                    if dof_name == "theta":
                        vector_obj.pos.theta = solved_value
                    elif dof_name == "phi":
                        vector_obj.pos.phi = solved_value
                    elif dof_name == "r":
                        vector_obj.pos.r = solved_value
                    else:
                        print(
                            f"Warning: Unknown DOF name '{dof_name}' in unknown_map "
                            f"for {analysis_type}."
                        )