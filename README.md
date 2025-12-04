# Automataii - Interactive Mechanism Design & Animation Platform

**Advanced mechanism design, simulation, and animation platform with real-time parametric editing capabilities.**

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![Qt](https://img.shields.io/badge/Qt-PyQt6%2FPySide6-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

## 🎯 Overview

Automataii is a sophisticated platform for designing, simulating, and animating mechanical systems. It combines advanced kinematics simulation with intuitive direct manipulation interfaces, enabling both engineers and researchers to create and explore complex mechanisms interactively.

### 🌟 Key Features

- **🔧 Mechanism Design**: Interactive design of 4-bar linkages, cam systems, and gear trains
- **🎮 Parametric Playground**: Real-time manipulation of mechanism parameters through drag-and-drop handles
- **📈 Kinematic Simulation**: Advanced forward/inverse kinematics with collision detection
- **🎬 Animation Pipeline**: Character animation from static drawings with mechanism-driven motion
- **🏗️ Modular Architecture**: Event-driven, dependency-injected architecture for extensibility
- **💾 Project Management**: Compressed .atii project format with version control

---

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/automataii/automataii.git
cd automataii

# Recommended: use uv for reproducible environments
uv sync
```

### Running the Application

```bash
# Launch Automataii GUI
uv run automataii
```

### Repository Layout

- `src/automataii` — core application packages, kept production-ready.
- `tests/` — automated test suites; long-running or hardware-bound scenarios now live under `tests/manual/` and are excluded from default `pytest` runs.
- `scripts/` — reproducible developer tooling (build, packaging, reporting).
- `packaging/pyinstaller` — PyInstaller specifications used by build scripts.
- `resources/` — runtime assets (blueprints, examples, icons) consumed through `resolve_path`.
- `docs/` — product requirements, operations notes, and generated reports (`docs/reports/`).
- `archive/` — legacy utilities and investigative artefacts retained for reference but not shipped.

Run manual tests explicitly when needed, for example:

```bash
pytest tests/manual/test_cam_mechanism.py
```

---

## 🎮 Parametric Editing System - **NOW FUNCTIONAL!**

> **✅ Latest Update (2025-06-23)**: Critical bugs in parametric handle creation have been fixed. The parametric editing system is now fully operational for 4-bar linkages.

### 🔥 Current Capabilities

#### **✅ 4-Bar Linkage Parametric Editing**
- **Ground Pivot Manipulation**: Bright red anchor handles for easy identification
- **Real-time Visual Feedback**: Immediate mechanism recalculation during manipulation
- **Constraint Validation**: Grashof's criterion and geometric constraints enforced
- **Performance Optimized**: 50ms update throttling for smooth interaction
- **Undo/Redo Support**: Command pattern implementation for parameter changes

#### **🎛️ How to Use Parametric Mode**
1. **Design/Load Mechanism**: Use the mechanism recommendation system or load existing mechanism
2. **Activate Parametric Mode**: Click the "Parametric Edit" button in the Mechanism Design Tab
3. **Manipulate Parameters**: Drag the bright red anchor handles to modify ground pivot positions
4. **Real-time Feedback**: See mechanism geometry update instantly as you drag
5. **Constraint Guidance**: System prevents invalid configurations automatically

#### **🏗️ Architecture Highlights**
```python
# Sophisticated parametric system structure
src/automataii/gui/tabs/mechanism_design/parametric/
├── controllers/parameter_controller.py    # 500+ lines of advanced control logic
├── handles/base_handle.py                # Abstract drag-and-drop foundation
├── handles/anchor_handle.py              # Specialized ground pivot manipulation
├── strategies/                           # Extensible strategy patterns
└── updaters/                            # Performance-optimized update system
```

### 🚧 Coming Soon - Enhanced Parametric Playground

The foundation is in place for a revolutionary parametric playground experience:

#### **🎯 Phase 1: Multi-Handle 4-Bar System**
- **Link Length Handles**: Direct manipulation of link lengths via bidirectional handles
- **Coupler Point Handles**: Interactive coupler curve design and optimization
- **Real-time Path Preview**: Ghost path overlay during parameter manipulation
- **Advanced Constraints**: Workspace boundaries, manufacturability limits

#### **🎯 Phase 2: Multi-Mechanism Support**
- **Cam Profile Editing**: Direct manipulation of cam profiles and follower motion
- **Gear System Controls**: Interactive gear ratio, center distance, and tooth profile editing
- **Planetary Gear Design**: Complete planetary gear system designer

#### **🎯 Phase 3: AI-Powered Playground**
- **ML Optimization**: Intelligent parameter suggestions for design goals
- **Physics-Based Interaction**: Momentum, elasticity, and force visualization
- **Collaborative Design**: Multi-user parametric editing sessions

---

## 🏗️ Architecture Overview

Automataii is built on a modern, modular architecture designed for performance and extensibility:

### **Core Systems**
- **Dependency Injection Container**: Manages component lifecycle and dependencies
- **Event-Driven Architecture**: Loose coupling with typed events and async processing
- **Redux-like State Management**: Immutable state with time-travel debugging
- **Qt Compatibility Layer**: Seamless PyQt6/PySide6 interoperability

### **Mechanism Engine**
- **Kinematic Solver**: Advanced forward/inverse kinematics with constraint handling
- **Parametric Controller**: Real-time parameter updates with performance optimization
- **Visual Pipeline**: High-performance rendering with Qt Graphics Framework
- **Simulation Engine**: Physics-based mechanism simulation and animation

### **Project Format (.atii)**
- **ZIP-based Container**: Compressed project files with atomic saves
- **Version Management**: Schema evolution and backward compatibility
- **Asset Integration**: Images, animations, and mechanism data in single file

---

## 📊 Mechanism Types Supported

| Mechanism Type | Design | Parametric Editing | Simulation | Status |
|---|---|---|---|---|
| **4-Bar Linkage** | ✅ Complete | ✅ **Functional** | ✅ Complete | **Ready** |
| **Cam Systems** | ✅ Complete | 🚧 In Development | ✅ Complete | **Partial** |
| **Gear Trains** | ✅ Complete | 🚧 Planned | ✅ Complete | **Partial** |
| **Planetary Gears** | 🚧 Planned | 🚧 Planned | 🚧 Planned | **Future** |

---

## 🧪 Development & Testing

### **Running Tests**
```bash
# Run all tests
pytest

# Run specific test categories
pytest tests/test_parametric_system.py
pytest tests/test_mechanism_simulation.py

# Run with coverage
pytest --cov=src/automataii tests/
```

### **Development Environment**
```bash
# Install development dependencies
uv sync

# Run linting
flake8 src/
black src/ tests/

# Type checking
mypy src/automataii/
```

### **Performance Profiling**
```bash
# Profile parametric system performance
python -m automataii.benchmarks.parametric_performance

# Memory usage analysis
python -m automataii.benchmarks.memory_analysis
```

---

## 📈 Performance Metrics

### **Parametric System Performance**
- **Handle Response Time**: < 16ms (60 FPS interactive feedback)
- **Parameter Update Frequency**: 50ms throttling (20 updates/second)
- **Constraint Validation**: < 10ms (instant feedback)
- **Memory Usage**: < 50MB for complex mechanisms

### **Simulation Performance**
- **Kinematic Solving**: < 1ms per frame
- **Visual Rendering**: Hardware-accelerated Qt Graphics
- **Animation Playback**: 60 FPS with smooth interpolation

---

## 🛠️ Configuration

### **Application Settings**
```python
# Located in: src/automataii/config/
MECHANISM_SETTINGS = {
    'parametric_update_throttle_ms': 50,
    'constraint_validation_enabled': True,
    'handle_visibility_radius': 20.0,
    'performance_monitoring': True
}

VISUAL_SETTINGS = {
    'mechanism_line_width': 3.0,
    'handle_colors': {
        'anchor': '#FF0000',  # Bright red
        'link': '#0080FF',    # Blue
        'constraint': '#FFD700'  # Gold
    }
}
```

### **Logging Configuration**
```python
# Detailed logging for debugging parametric system
LOGGING_CONFIG = {
    'level': 'DEBUG',
    'handlers': ['console', 'file'],
    'parametric_debug': True,
    'performance_tracking': True
}
```

---

## 🤝 Contributing

We welcome contributions to enhance the parametric playground and expand mechanism support!

### **Contribution Areas**
1. **Parametric Handle Types**: Implement new manipulation handles (link length, angle, etc.)
2. **Mechanism Support**: Add cam profile and gear manipulation capabilities
3. **Constraint Systems**: Develop advanced constraint validation and optimization
4. **Performance Optimization**: Improve real-time update performance
5. **User Experience**: Enhance interaction paradigms and visual feedback

### **Development Workflow**
```bash
# Fork the repository and create feature branch
git checkout -b feature/enhanced-parametric-handles

# Make changes and test thoroughly
pytest tests/test_parametric_*.py

# Submit pull request with detailed description
```

### **Code Standards**
- **Type Hints**: Full type annotation required
- **Documentation**: Docstrings for all public APIs
- **Testing**: Unit tests for new functionality
- **Performance**: Benchmark critical path changes

---

## 📚 Documentation

### **User Guides**
- [Getting Started with Parametric Design](docs/user_guides/parametric_quickstart.md)
- [Advanced Mechanism Design](docs/user_guides/advanced_mechanisms.md)
- [Animation and Simulation](docs/user_guides/animation_workflow.md)

### **Developer Documentation**
- [Architecture Overview](docs/ARCHITECTURE_SUMMARY.md)
- [Parametric System Design](docs/technical/parametric_architecture.md)
- [API Reference](docs/api/index.md)

### **Research Publications**
- [Interactive Mechanism Design Through Direct Manipulation](docs/research/direct_manipulation.pdf)
- [Performance Optimization in Real-time Parametric Systems](docs/research/performance_optimization.pdf)

---

## 🎯 Roadmap

### **Q4 2025: Enhanced Parametric Playground**
- [ ] Multi-handle 4-bar linkage manipulation
- [ ] Real-time path preview and optimization
- [ ] Advanced constraint visualization
- [ ] Performance benchmarking suite

### **Q1 2026: Multi-Mechanism Support**
- [ ] Cam profile parametric editing
- [ ] Gear system interactive design
- [ ] Unified mechanism manipulation interface
- [ ] Cross-mechanism constraint handling

### **Q2 2026: AI-Powered Design**
- [ ] ML-based parameter optimization
- [ ] Intelligent design suggestions
- [ ] Automated constraint solving
- [ ] Design pattern recognition

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Research Foundation**: Built on cutting-edge research in computational design and human-computer interaction
- **Open Source Community**: Leveraging PyQt6, NumPy, SciPy, and other excellent open source libraries
- **Design Philosophy**: Inspired by Ivan Sutherland's Sketchpad and modern direct manipulation principles

---

## 📞 Support & Contact

- **Issues**: [GitHub Issues](https://github.com/your-org/automataii/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/automataii/discussions)
- **Email**: automataii-support@your-org.com
- **Documentation**: [Full Documentation](https://automataii-docs.your-org.com)

---

**Built with ❤️ for mechanical engineers, researchers, and anyone passionate about understanding how things move.**
