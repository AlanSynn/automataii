"""
Physics-based Mechanism Simulations

Provides pre-built physics simulations for common mechanisms.
"""

import numpy as np
from typing import List, Dict, Tuple, Optional

from .engine import PhysicsEngine
from .body import RigidBody, LinkageBody, GearBody, BodyType
from .constraints import Joint, SpringConstraint, MotorConstraint


class PhysicsMechanism:
    """Base class for physics-based mechanisms"""
    
    def __init__(self, engine: PhysicsEngine):
        self.engine = engine
        self.bodies: List[RigidBody] = []
        self.constraints = []
        self.parameters: Dict[str, float] = {}
        
    def create(self) -> None:
        """Create the mechanism in the physics world"""
        pass
        
    def update_parameters(self, params: Dict[str, float]) -> None:
        """Update mechanism parameters"""
        self.parameters.update(params)
        
    def get_body_positions(self) -> Dict[str, Tuple[float, float]]:
        """Get positions of all bodies"""
        positions = {}
        for i, body in enumerate(self.bodies):
            if body:
                positions[f"body_{i}"] = tuple(body.position)
        return positions
        
    def reset(self) -> None:
        """Reset mechanism to initial state"""
        for body in self.bodies:
            if body:
                body.reset()


class FourBarLinkage(PhysicsMechanism):
    """Physics simulation of a four-bar linkage mechanism"""
    
    def __init__(self, engine: PhysicsEngine, 
                 a: float = 2.0, b: float = 3.0, c: float = 4.0, d: float = 3.5):
        """
        Initialize four-bar linkage.
        
        Args:
            engine: Physics engine
            a: Length of input link
            b: Length of coupler link  
            c: Length of output link
            d: Length of ground link
        """
        super().__init__(engine)
        self.parameters = {'a': a, 'b': b, 'c': c, 'd': d, 'input_speed': 1.0}
        
    def create(self) -> None:
        """Create four-bar linkage in physics world"""
        a, b, c, d = self.parameters['a'], self.parameters['b'], self.parameters['c'], self.parameters['d']
        
        # Ground points
        ground_1 = (0, 0)
        ground_2 = (d, 0)
        
        # Create bodies
        # Input link (crank)
        input_link = LinkageBody(
            length=a,
            position=(a/2, 0),
            mass=1.0,
            body_type=BodyType.DYNAMIC
        )
        self.bodies.append(input_link)
        self.engine.add_body(input_link)
        
        # Coupler link
        coupler_link = LinkageBody(
            length=b,
            position=(a + b/2, 0),
            mass=2.0,
            body_type=BodyType.DYNAMIC
        )
        self.bodies.append(coupler_link)
        self.engine.add_body(coupler_link)
        
        # Output link (rocker)
        output_link = LinkageBody(
            length=c,
            position=(d - c/2, 0),
            mass=1.5,
            body_type=BodyType.DYNAMIC
        )
        self.bodies.append(output_link)
        self.engine.add_body(output_link)
        
        # Ground body (static)
        ground_body = RigidBody(
            position=(d/2, 0),
            mass=1.0,
            body_type=BodyType.STATIC
        )
        self.bodies.append(ground_body)
        self.engine.add_body(ground_body)
        
        # Create joints
        # Input link to ground
        joint_1 = Joint(
            input_link, ground_body,
            anchor_a=(-a/2, 0),  # Start of input link
            anchor_b=(-d/2, 0)   # Ground point 1
        )
        self.constraints.append(joint_1)
        self.engine.add_joint(joint_1)
        
        # Input link to coupler
        joint_2 = Joint(
            input_link, coupler_link,
            anchor_a=(a/2, 0),   # End of input link
            anchor_b=(-b/2, 0)   # Start of coupler
        )
        self.constraints.append(joint_2)
        self.engine.add_joint(joint_2)
        
        # Coupler to output link
        joint_3 = Joint(
            coupler_link, output_link,
            anchor_a=(b/2, 0),   # End of coupler
            anchor_b=(c/2, 0)    # End of output link
        )
        self.constraints.append(joint_3)  
        self.engine.add_joint(joint_3)
        
        # Output link to ground
        joint_4 = Joint(
            output_link, ground_body,
            anchor_a=(-c/2, 0),  # Start of output link
            anchor_b=(d/2, 0)    # Ground point 2
        )
        self.constraints.append(joint_4)
        self.engine.add_joint(joint_4)
        
        # Add motor to input link
        motor = MotorConstraint(
            input_link,
            target_velocity=self.parameters['input_speed'],
            max_torque=50.0
        )
        self.constraints.append(motor)
        self.engine.add_joint(motor)  # Motors are treated as constraints
        
    def update_parameters(self, params: Dict[str, float]) -> None:
        """Update linkage parameters"""
        super().update_parameters(params)
        
        # Update motor speed if changed
        if 'input_speed' in params and len(self.constraints) > 4:
            motor = self.constraints[4]  # Motor is the 5th constraint
            if isinstance(motor, MotorConstraint):
                motor.set_target_velocity(params['input_speed'])


class SliderCrank(PhysicsMechanism):
    """Physics simulation of slider-crank mechanism"""
    
    def __init__(self, engine: PhysicsEngine, crank_length: float = 2.0, rod_length: float = 4.0):
        super().__init__(engine)
        self.parameters = {
            'crank_length': crank_length,
            'rod_length': rod_length,
            'input_speed': 2.0
        }
        
    def create(self) -> None:
        """Create slider-crank mechanism"""
        r = self.parameters['crank_length']
        l = self.parameters['rod_length']
        
        # Crank
        crank = LinkageBody(
            length=r,
            position=(r/2, 0),
            mass=1.0,
            body_type=BodyType.DYNAMIC
        )
        self.bodies.append(crank)
        self.engine.add_body(crank)
        
        # Connecting rod
        rod = LinkageBody(
            length=l,
            position=(r + l/2, 0),
            mass=2.0,
            body_type=BodyType.DYNAMIC
        )
        self.bodies.append(rod)
        self.engine.add_body(rod)
        
        # Slider (piston)
        slider = RigidBody(
            position=(r + l, 0),
            mass=1.5,
            body_type=BodyType.DYNAMIC
        )
        self.bodies.append(slider)
        self.engine.add_body(slider)
        
        # Ground
        ground = RigidBody(
            position=(0, 0),
            mass=1.0,
            body_type=BodyType.STATIC
        )
        self.bodies.append(ground)
        self.engine.add_body(ground)
        
        # Joints
        # Crank to ground (revolute)
        crank_joint = Joint(crank, ground, anchor_a=(-r/2, 0), anchor_b=(0, 0))
        self.constraints.append(crank_joint)
        self.engine.add_joint(crank_joint)
        
        # Crank to rod
        crank_rod_joint = Joint(crank, rod, anchor_a=(r/2, 0), anchor_b=(-l/2, 0))
        self.constraints.append(crank_rod_joint)
        self.engine.add_joint(crank_rod_joint)
        
        # Rod to slider
        rod_slider_joint = Joint(rod, slider, anchor_a=(l/2, 0), anchor_b=(0, 0))
        self.constraints.append(rod_slider_joint)
        self.engine.add_joint(rod_slider_joint)
        
        # Motor on crank
        motor = MotorConstraint(crank, self.parameters['input_speed'])
        self.constraints.append(motor)
        self.engine.add_joint(motor)


class GearTrain(PhysicsMechanism):
    """Physics simulation of gear train"""
    
    def __init__(self, engine: PhysicsEngine, gear_radii: List[float] = None):
        super().__init__(engine)
        if gear_radii is None:
            gear_radii = [1.0, 1.5, 0.8]
        self.parameters = {
            'gear_radii': gear_radii,
            'input_speed': 3.0,
            'gear_spacing': 0.1
        }
        
    def create(self) -> None:
        """Create gear train"""
        radii = self.parameters['gear_radii']
        spacing = self.parameters['gear_spacing']
        
        # Create gears
        x_pos = 0
        for i, radius in enumerate(radii):
            gear = GearBody(
                radius=radius,
                position=(x_pos, 0),
                mass=radius * 2,  # Mass proportional to size
                body_type=BodyType.DYNAMIC if i > 0 else BodyType.DYNAMIC
            )
            self.bodies.append(gear)
            self.engine.add_body(gear)
            
            # Position next gear
            if i < len(radii) - 1:
                x_pos += radius + radii[i + 1] + spacing
                
        # Ground for first gear
        ground = RigidBody(position=(0, 0), body_type=BodyType.STATIC)
        self.bodies.append(ground)
        self.engine.add_body(ground)
        
        # Pin first gear to ground
        first_gear_joint = Joint(self.bodies[0], ground, anchor_a=(0, 0), anchor_b=(0, 0))
        self.constraints.append(first_gear_joint)
        self.engine.add_joint(first_gear_joint)
        
        # Add motor to first gear
        motor = MotorConstraint(self.bodies[0], self.parameters['input_speed'])
        self.constraints.append(motor)
        self.engine.add_joint(motor)
        
        # Create gear coupling constraints (simplified)
        for i in range(len(radii) - 1):
            gear_a = self.bodies[i]
            gear_b = self.bodies[i + 1]
            
            # Simple gear coupling - maintain velocity ratio
            # This is a simplified approach; real gear meshing is more complex
            pass


class SpringMassDamper(PhysicsMechanism):
    """Physics simulation of spring-mass-damper system"""
    
    def __init__(self, engine: PhysicsEngine, mass: float = 2.0, k: float = 100.0, c: float = 10.0):
        super().__init__(engine)
        self.parameters = {
            'mass': mass,
            'spring_constant': k,
            'damping': c,
            'rest_length': 3.0
        }
        
    def create(self) -> None:
        """Create spring-mass-damper system"""
        mass = self.parameters['mass']
        k = self.parameters['spring_constant']
        c = self.parameters['damping']
        rest_length = self.parameters['rest_length']
        
        # Mass
        mass_body = RigidBody(
            position=(rest_length, 0),
            mass=mass,
            body_type=BodyType.DYNAMIC
        )
        self.bodies.append(mass_body)
        self.engine.add_body(mass_body)
        
        # Ground anchor
        ground = RigidBody(
            position=(0, 0),
            body_type=BodyType.STATIC
        )
        self.bodies.append(ground)
        self.engine.add_body(ground)
        
        # Spring
        spring = SpringConstraint(
            ground, mass_body,
            anchor_a=(0, 0),
            anchor_b=(0, 0),
            rest_length=rest_length,
            stiffness=k,
            damping=c
        )
        self.constraints.append(spring)
        self.engine.add_spring(spring)


def create_mechanism(mechanism_type: str, engine: PhysicsEngine, **kwargs) -> Optional[PhysicsMechanism]:
    """
    Factory function to create physics mechanisms.
    
    Args:
        mechanism_type: Type of mechanism to create
        engine: Physics engine
        **kwargs: Mechanism-specific parameters
        
    Returns:
        Created mechanism or None if type not found
    """
    mechanisms = {
        'four_bar_linkage': FourBarLinkage,
        'slider_crank': SliderCrank,
        'gear_train': GearTrain,
        'spring_mass_damper': SpringMassDamper
    }
    
    if mechanism_type in mechanisms:
        mechanism = mechanisms[mechanism_type](engine, **kwargs)
        mechanism.create()
        return mechanism
        
    return None