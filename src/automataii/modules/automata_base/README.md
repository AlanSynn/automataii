# Automata Base Module

A modular system for defining and configuring mechanical automata bases, including mounting types, dimensions, and assembly methods.

## Features

- **Multiple Base Types**: Support for flat, box, pedestal, wall-mounted, and modular bases
- **Material Options**: Wood, MDF, acrylic, metal, 3D-printed plastics, and more
- **Assembly Methods**: Screws, glue, snap-fit, interlocking, and other assembly techniques
- **Mounting Types**: Surface, wall, ceiling, pedestal, clamp, magnetic, and freestanding options
- **Dimension Models**: 2D and 3D dimension support with unit conversions
- **Export Formats**: SVG and DXF export for fabrication
- **Validation**: Comprehensive validation of configurations

## Installation

```bash
# Install from the module directory
pip install -e .

# Or install with development dependencies
pip install -e ".[dev]"
```

## Quick Start

```python
from automata_base import BaseType, MaterialType, get_base_specification

# Use a predefined specification
spec = get_base_specification("simple_flat")
base = spec.create_base(
    size_name="medium",
    material=MaterialType.WOOD
)

# Or create a custom configuration
from automata_base import BaseConfiguration, Dimensions2D, Unit

custom_base = BaseConfiguration(
    name="My Custom Base",
    base_type=BaseType.FLAT_RECTANGULAR,
    dimensions=Dimensions2D(width=250, height=180, unit=Unit.MM),
    primary_material=MaterialType.ACRYLIC,
    material_thickness=6.0
)

# Export to SVG
from automata_base.utils import base_to_svg
svg_content = base_to_svg(custom_base, show_mounting_points=True)
```

## Base Types

- `FLAT_RECTANGULAR`: Simple flat rectangular base
- `FLAT_CIRCULAR`: Flat circular base
- `BOX_ENCLOSED`: Fully enclosed box base
- `BOX_OPEN`: Open-top box base
- `PEDESTAL`: Vertical pedestal base
- `WALL_MOUNTED`: Wall-mountable base
- `MODULAR`: Modular base system with interchangeable parts
- `CUSTOM`: Custom base design

## Materials

The module supports various materials with properties:
- Wood types (wood, MDF, plywood)
- Plastics (acrylic, 3D-printed)
- Metals (aluminum, steel)
- Others (cardboard, composite)

Each material has properties like density, strength, cost, and workability.

## Assembly Methods

- `SCREWS`: Standard screw assembly
- `GLUE`: Adhesive bonding
- `SNAP_FIT`: Snap-together parts
- `INTERLOCKING`: Interlocking joints
- `WELDING`: Welded connections
- `MAGNETIC`: Magnetic assembly
- `PRESS_FIT`: Press-fit connections
- `BOLTS`: Bolt assembly
- `RIVETS`: Riveted connections

## API Reference

### Core Classes

- `BaseConfiguration`: Main configuration class
- `Dimensions2D` / `Dimensions3D`: Dimension models
- `BaseSpecification`: Predefined base specifications
- `AssemblyInfo`: Assembly instructions and components

### Enumerations

- `BaseType`: Available base types
- `MaterialType`: Material options
- `MountingType`: Mounting methods
- `AssemblyMethod`: Assembly techniques
- `ConnectionType`: Connection types for modular systems

### Utilities

- `validate_base_configuration()`: Validate configurations
- `base_to_svg()`: Export to SVG format
- `base_to_dxf()`: Export to DXF format

## Contributing

See the main Automataii project for contribution guidelines.

## License

MIT License - see the main project for details.