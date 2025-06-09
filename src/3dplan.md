# Automataii 3D Extension Plan

## Executive Summary
This document outlines the comprehensive plan for extending Automataii from 2D to 3D, enabling users to create 3D animated mechanical automata from 2D character images.

## 1. Core Architecture Changes

### 1.1 3D Coordinate System
```python
# Current 2D system
Point2D = (x, y)
Transform2D = (position, rotation, scale)

# New 3D system
Point3D = (x, y, z)
Transform3D = (position, rotation, scale)  # rotation as quaternion
```

### 1.2 New Core Classes
- `Vector3D`: 3D vector mathematics
- `Quaternion`: Rotation representation
- `Matrix4x4`: Transformation matrices
- `Mesh3D`: 3D mesh representation
- `Camera3D`: 3D viewport camera

## 2. 3D Rendering Pipeline

### 2.1 Graphics Engine Integration
**Option 1: PyQt3D (Qt 3D)**
```python
from PyQt6.Qt3DCore import QEntity, QTransform
from PyQt6.Qt3DRender import QMesh, QMaterial
from PyQt6.Qt3DExtras import Qt3DWindow
```

**Option 2: VTK (Visualization Toolkit)**
```python
import vtk
from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
```

**Option 3: Vispy (Modern OpenGL)**
```python
import vispy.scene
from vispy.scene import SceneCanvas, visuals
```

**Recommendation**: PyQt3D for seamless integration with existing PyQt6 infrastructure.

### 2.2 3D View Components
```python
class Editor3DView(Qt3DWindow):
    """3D viewport for editing and visualization"""
    - Camera controls (orbit, pan, zoom)
    - Object selection and manipulation
    - Grid and axis helpers
    - Lighting setup
    
class Mechanism3DRenderer:
    """Renders 3D mechanisms"""
    - Joint visualization
    - Link rendering
    - Motion path display
    - Animation playback
```

## 3. 2D to 3D Conversion Pipeline

### 3.1 Depth Estimation
```python
class DepthEstimator:
    """Estimates depth from 2D images"""
    
    def estimate_depth_ml(self, image):
        # Use MiDaS or DPT models
        model = torch.hub.load('intel-isl/MiDaS')
        return model(image)
    
    def estimate_depth_skeleton(self, skeleton_2d):
        # Use anthropometric constraints
        return self.apply_bone_length_constraints(skeleton_2d)
```

### 3.2 3D Reconstruction
```python
class CharacterReconstructor3D:
    """Reconstructs 3D character from 2D parts"""
    
    def reconstruct_from_parts(self, parts_2d, depth_map):
        # 1. Create mesh for each part
        # 2. Apply depth information
        # 3. Connect parts at joints
        # 4. Generate UV mapping
        
    def create_part_mesh(self, part_2d, depth):
        # Extrude 2D shape along depth
        # Add thickness based on part type
        # Smooth edges and corners
```

### 3.3 Texture Projection
```python
class TextureProjector:
    """Projects 2D textures onto 3D meshes"""
    
    def project_texture(self, texture_2d, mesh_3d):
        # UV unwrapping
        # Texture coordinate generation
        # Handle occlusions and seams
```

## 4. 3D Skeleton System

### 4.1 3D Skeleton Model
```python
class Skeleton3D:
    joints: Dict[str, Joint3D]
    bones: List[Bone3D]
    
class Joint3D:
    name: str
    position: Vector3D
    rotation: Quaternion
    parent: Optional[Joint3D]
    constraints: JointConstraints3D
    
class Bone3D:
    start_joint: Joint3D
    end_joint: Joint3D
    length: float
    twist: float
```

### 4.2 IK Solver for 3D
```python
class IKSolver3D:
    """3D Inverse Kinematics solver"""
    
    def solve_chain(self, chain: List[Joint3D], target: Vector3D):
        # FABRIK algorithm extended to 3D
        # CCD (Cyclic Coordinate Descent) for 3D
        # Handle joint constraints
```

## 5. 3D Mechanism Generation

### 5.1 3D Linkage Mechanisms
```python
class FourBarLinkage3D:
    """3D four-bar linkage with spatial movement"""
    
    def generate(self, motion_path_3d):
        # Spatial linkage synthesis
        # Handle out-of-plane motion
        # Spherical joints for 3D rotation
        
class SphericalMechanism:
    """Spherical four-bar for 3D rotation"""
    
class SpatialMechanism:
    """General spatial mechanisms (RSSR, RSSP)"""
```

### 5.2 3D Cam Mechanisms
```python
class CylindricalCam:
    """Cylindrical cam for 3D motion"""
    
class GlobalCam:
    """Globoidal cam for complex 3D paths"""
```

### 5.3 3D Gear Systems
```python
class BevelGear:
    """Bevel gears for perpendicular shafts"""
    
class WormGear:
    """Worm gears for high reduction ratios"""
    
class HelicalGear:
    """Helical gears for smooth operation"""
```

## 6. 3D Animation System

### 6.1 3D Motion Paths
```python
class MotionPath3D:
    points: List[Vector3D]
    tangents: List[Vector3D]
    
    def interpolate(self, t: float) -> Transform3D:
        # Spline interpolation in 3D
        # Handle orientation along path
```

### 6.2 3D Physics Simulation
```python
class Physics3D:
    """3D physics for realistic motion"""
    
    def simulate_dynamics(self, mechanism):
        # Mass and inertia calculations
        # Collision detection
        # Joint forces and torques
```

## 7. User Interface Updates

### 7.1 3D Editing Tools
```python
class TransformGizmo3D:
    """3D manipulation handles"""
    - Translation arrows
    - Rotation rings
    - Scale handles
    
class PathDrawing3D:
    """3D path drawing tools"""
    - Planar drawing mode
    - Free 3D drawing
    - Curve projection tools
```

### 7.2 View Controls
- Multiple viewport layouts (top, front, side, perspective)
- Camera bookmarks
- Stereoscopic view support
- VR preview mode

## 8. File Format and Data Management

### 8.1 3D Project Structure
```yaml
project_3d:
  version: "2.0"
  mode: "3D"
  
  character:
    mesh_files: ["part1.obj", "part2.obj"]
    textures: ["texture1.png", "texture2.png"]
    skeleton: "skeleton.json"
    
  mechanisms:
    - type: "spatial_fourbar"
      parameters: {...}
      
  animation:
    fps: 30
    duration: 2.0
    keyframes: [...]
```

### 8.2 Export Formats
- **3D Printing**: STL, OBJ with mechanism assembly instructions
- **Animation**: FBX, GLTF with embedded animations
- **CAD**: STEP files for further engineering
- **Simulation**: URDF for robotics simulation

## 9. Performance Optimization

### 9.1 Rendering Optimization
- Level-of-detail (LOD) system
- Frustum culling
- Instanced rendering for repeated parts
- GPU-based skinning

### 9.2 Computation Optimization
- Parallel IK solving
- Spatial partitioning for collision detection
- Mechanism constraint caching

## 10. Implementation Roadmap

### Phase 1: Foundation (3 months)
1. 3D math library implementation
2. 3D rendering pipeline setup
3. Basic 3D viewport integration
4. 3D coordinate system throughout codebase

### Phase 2: 2D-to-3D Pipeline (4 months)
1. Depth estimation integration
2. Mesh generation from 2D parts
3. 3D skeleton creation
4. Texture mapping system

### Phase 3: 3D Mechanisms (4 months)
1. 3D IK solver implementation
2. Spatial mechanism generators
3. 3D motion path tools
4. Physics simulation integration

### Phase 4: Polish and Tools (3 months)
1. Advanced 3D editing tools
2. Multi-viewport support
3. Export pipeline
4. Performance optimization

### Phase 5: Advanced Features (2 months)
1. VR preview support
2. 3D printing optimization
3. Advanced materials and lighting
4. Procedural animation tools

## 11. Technical Dependencies

### Required Libraries
```python
# 3D Graphics
PyQt3D >= 6.0
numpy >= 1.20  # Already have
scipy >= 1.7   # For 3D interpolation

# Depth Estimation
torch >= 1.9
timm >= 0.4.5  # For vision transformers
opencv-python >= 4.5  # Already have

# 3D File I/O
trimesh >= 3.9  # Mesh processing
pymeshlab >= 2021.10  # Mesh optimization

# Optional
pybullet >= 3.2  # Physics simulation
moderngl >= 5.6  # Alternative renderer
```

### Hardware Requirements
- **Minimum**: OpenGL 3.3 support, 4GB VRAM
- **Recommended**: OpenGL 4.5, 8GB VRAM, CUDA-capable GPU

## 12. Migration Strategy

### Backward Compatibility
- Maintain 2D mode as default
- Automatic 2D project import with depth estimation
- Gradual UI transition with mode toggle

### Code Architecture
```python
# Abstract base classes for 2D/3D compatibility
class TransformBase(ABC):
    @abstractmethod
    def apply(self, point): pass

class Transform2D(TransformBase):
    # Existing implementation

class Transform3D(TransformBase):
    # New 3D implementation
```

## 13. Testing Strategy

### Unit Tests
- 3D math operations
- Coordinate transformations
- Mechanism kinematics

### Integration Tests
- 2D to 3D conversion pipeline
- Rendering pipeline
- Animation system

### Performance Tests
- Frame rate benchmarks
- Memory usage profiling
- Large project handling

## 14. Documentation Requirements

### Developer Documentation
- 3D API reference
- Migration guide for plugins
- Performance best practices

### User Documentation
- 3D interface tutorials
- Mechanism design in 3D
- Export workflow guides

## 15. Risk Mitigation

### Technical Risks
1. **Performance degradation**: Implement aggressive LOD and culling
2. **Complexity explosion**: Maintain clean separation of 2D/3D code
3. **Learning curve**: Provide intuitive 2D-to-3D transition tools

### Mitigation Strategies
- Incremental rollout with feature flags
- Extensive beta testing program
- Fallback to 2D mode for unsupported features

## Conclusion

This plan provides a comprehensive roadmap for extending Automataii to 3D while maintaining its core simplicity and user-friendliness. The modular approach allows for incremental implementation and testing, ensuring a smooth transition for existing users while opening up exciting new possibilities for 3D mechanical animation.