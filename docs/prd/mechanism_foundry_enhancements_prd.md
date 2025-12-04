# Mechanism Foundry Educational Enhancements PRD

**Author:** Automataii Contributors  
**Status:** Proposed (2025-10-24)  
**Related:** `docs/prd/mechanism_foundry_modularization_prd.md`, `SESSION_FOUNDRY_UI_ENHANCEMENTS.md`

---

## 1. Problem / Goal

**Problem:**
- Current Foundry tab requires users to understand mechanisms before interacting
- No visual preview of motion paths during parameter adjustment
- Mechanism selection is dropdown-only (no visual discovery)
- Info panel lacks educational depth (advantages, cautions, parts, materials)
- Difficult for beginners to understand mechanism behavior without running animation
- No "explore and discover" workflow for browsing mechanism catalog

**Goal:**
Transform Mechanism Foundry into an educational platform with three major enhancements:
1. **Motion Path Hover Preview** - instant trajectory visualization
2. **Mechanism Gallery Landing Page** - visual catalog with animated previews
3. **Enhanced Educational Info Panel** - comprehensive mechanism documentation

**Quantitative Targets:**
- Gallery page load time: ≤500ms for 4 mechanism thumbnails
- Hover preview latency: ≤50ms from hover to path display
- Path computation cache hit rate: ≥95%
- Thumbnail animation: 30fps (33ms per frame)
- Info panel content: ≤5 parts per mechanism (digestible)
- Module size: Each new module ≤300 LOC
- User discovery time: ≤30s to explore all mechanisms (vs. current ~2min)

---

## 2. In-Scope / Out-of-Scope

### In-Scope

#### Feature 1: Motion Path Hover Preview
1. Hover interaction on mechanism visualization
2. Display complete trajectory path for key points (coupler, output, follower)
3. Point-by-point markers along path
4. Cached path computation (avoid recalculating on every hover)
5. Toggle on/off via toolbar action
6. Visual styling: dashed lines, faint markers, complementary colors

#### Feature 2: Mechanism Gallery Landing Page
1. Grid layout showing all available mechanisms
2. Animated preview for each mechanism (looping)
3. Thumbnail generation (snapshot at multiple angles)
4. Click to select → transition to parametric editing view
5. Visual categories (linkages, cams, gears)
6. Mechanism metadata display (name, complexity, tags)
7. Back button to return from editing view to gallery

#### Feature 3: Enhanced Educational Info Panel
1. Structured content format with sections:
   - **Title**: Mechanism name with variant identifier
   - **Goal**: Simple 1-2 sentence description
   - **Adjustable Parameters**: UI-friendly labels and discrete options
   - **Mechanism Visualization**: Diagram with arrows/rotation indicators
   - **Parts List**: ≤5 key components
   - **Advantages**: 2-3 bullet points
   - **Disadvantages/Limitations**: 2-3 bullet points
   - **Materials**: Fabrication suggestions (3D printing, laser cutting, etc.)
   - **Cautions**: Safety and operational warnings
2. JSON-based content definition (separate from code)
3. Support for discrete parameter options (small/medium/large)
4. HTML rendering with images/diagrams
5. Responsive layout (adapts to panel width)

### Out-of-Scope
- 3D visualization or WebGL rendering
- Video export of motion paths
- Interactive path editing (dragging trajectory)
- Multi-mechanism comparison view
- Real-time physics simulation beyond current kinematics
- Mobile/touch optimization (desktop-first)
- User-generated content or community catalog
- Advanced rendering (shadows, textures, realistic materials)
- Export to STL or CAD formats (covered elsewhere)

---

## 3. Success Metrics & Validation

### Structural Metrics
- Gallery module: ≤300 LOC
- Path preview module: ≤250 LOC
- Educational content module: ≤200 LOC
- Info panel renderer: ≤150 LOC
- JSON content files: ≤100 lines per mechanism
- Zero regression in existing Foundry functionality

### Quality Metrics
- **Gallery Performance:**
  - Thumbnail render: ≤100ms per mechanism
  - Gallery load: ≤500ms total
  - Smooth scrolling: 60fps (16.67ms per frame)
  
- **Path Preview Performance:**
  - Hover response: ≤50ms
  - Path compute: ≤10ms (first time), ≤1ms (cached)
  - Cache hit rate: ≥95%
  - Memory overhead: ≤500KB per mechanism path cache

- **Info Panel Quality:**
  - Content completeness: 100% of 4 mechanisms documented
  - Image load time: ≤200ms
  - Panel update latency: ≤50ms on parameter change
  - Readability score: ≥80 (Flesch Reading Ease)

- **User Experience:**
  - Discovery time: ≤30s to view all mechanisms
  - Selection clarity: 100% users can identify mechanism type
  - Educational value: Users can list ≥3 parts and ≥2 advantages per mechanism

### Validation Methods
1. Performance profiling with Qt performance tools
2. User testing with 5 users (novice to expert)
3. A/B testing: gallery vs. dropdown selection
4. Cache hit rate monitoring via telemetry
5. Screenshot regression tests for gallery thumbnails
6. Manual verification of educational content accuracy

---

## 4. Architecture Overview

### Directory Structure
```
src/automataii/
├── ui/tabs/mechanism_foundry/
│   ├── foundry_view.py                    # Main view (existing, ~575 LOC)
│   ├── gallery_view.py                    # NEW: Gallery landing page (~250 LOC)
│   ├── gallery_thumbnail.py               # NEW: Animated thumbnail widget (~150 LOC)
│   ├── path_preview.py                    # NEW: Motion path overlay (~200 LOC)
│   └── info_panel.py                      # NEW: Educational info renderer (~150 LOC)
├── application/mechanism_foundry/
│   ├── controller.py                      # Existing controller
│   ├── path_cache.py                      # NEW: Path computation cache (~100 LOC)
│   └── content_loader.py                  # NEW: Educational content loader (~80 LOC)
└── resources/
    └── mechanism_content/
        ├── four_bar.json                  # NEW: Educational content
        ├── cam_follower.json              # NEW: Educational content
        ├── slider_crank.json              # NEW: Educational content
        ├── gear_train.json                # NEW: Educational content
        └── diagrams/                      # NEW: Mechanism diagrams
            ├── four_bar_diagram.svg
            ├── cam_follower_diagram.svg
            └── ...
```

### Layering & Dependencies
```
UI Layer
  foundry_view.py ──┬──> gallery_view.py ──> gallery_thumbnail.py
                    ├──> path_preview.py
                    └──> info_panel.py

Application Layer
  controller.py ──┬──> path_cache.py
                  └──> content_loader.py

Data Layer
  resources/mechanism_content/*.json
```

### Key Abstractions

#### 1. Motion Path Cache (`path_cache.py`)
```python
@dataclass(frozen=True)
class PathCacheKey:
    mechanism_type: str
    parameters: tuple[tuple[str, float], ...]  # Hashable params
    point_name: str  # "coupler_point", "output_joint", etc.

@dataclass(frozen=True)
class CachedPath:
    points: tuple[tuple[float, float], ...]  # (x, y) coordinates
    angles: tuple[float, ...]  # Input angles for each point
    timestamp: float  # For LRU eviction

class PathCache:
    def __init__(self, max_size_mb: int = 10):
        self._cache: dict[PathCacheKey, CachedPath] = {}
        self._max_size = max_size_mb * 1024 * 1024
    
    def get(self, key: PathCacheKey) -> CachedPath | None: ...
    def put(self, key: PathCacheKey, path: CachedPath) -> None: ...
    def invalidate(self, mechanism_type: str) -> None: ...
    def compute_and_cache(
        self, 
        mechanism: Mechanism,
        parameters: dict[str, float],
        point_name: str,
        angle_samples: int = 360
    ) -> CachedPath: ...
```

#### 2. Educational Content (`content_loader.py`)
```python
@dataclass(frozen=True)
class ParameterOption:
    value: float
    label: str  # "Small", "Medium", "Large"
    description: str | None = None

@dataclass(frozen=True)
class MechanismContent:
    title: str
    goal: str
    parts: tuple[str, ...]  # Max 5 items
    advantages: tuple[str, ...]
    disadvantages: tuple[str, ...]
    materials: tuple[str, ...]
    cautions: tuple[str, ...]
    parameter_options: dict[str, tuple[ParameterOption, ...]]
    diagram_path: str | None

class ContentLoader:
    def load_content(self, mechanism_type: str) -> MechanismContent: ...
    def list_available_content(self) -> list[str]: ...
```

#### 3. Gallery Thumbnail (`gallery_thumbnail.py`)
```python
class GalleryThumbnail(QWidget):
    clicked = pyqtSignal(str)  # mechanism_type
    
    def __init__(
        self,
        mechanism_type: str,
        display_name: str,
        preview_config: PreviewConfig,
    ):
        self._mechanism: Mechanism = ...
        self._scene: QGraphicsScene = ...
        self._animation_timer: QTimer = ...
        self._current_angle: float = 0.0
    
    def start_animation(self) -> None: ...
    def stop_animation(self) -> None: ...
    def _render_frame(self) -> None: ...
```

#### 4. Path Preview Overlay (`path_preview.py`)
```python
class PathPreviewOverlay:
    def __init__(
        self,
        scene: QGraphicsScene,
        cache: PathCache,
    ):
        self._scene = scene
        self._cache = cache
        self._visible = False
        self._path_items: list[QGraphicsItem] = []
    
    def show_path(
        self,
        mechanism: Mechanism,
        parameters: dict[str, float],
        point_name: str,
    ) -> None: ...
    
    def hide_path(self) -> None: ...
    
    def toggle_visibility(self) -> None: ...
    
    def _draw_path(self, cached_path: CachedPath) -> None: ...
```

#### 5. Info Panel (`info_panel.py`)
```python
class EducationalInfoPanel(QWidget):
    def __init__(self):
        self._content_loader = ContentLoader()
        self._text_edit = QTextEdit()
        self._current_mechanism: str | None = None
    
    def update_content(
        self,
        mechanism_type: str,
        current_parameters: dict[str, float],
    ) -> None: ...
    
    def _render_html(
        self,
        content: MechanismContent,
        parameters: dict[str, float],
    ) -> str: ...
```

### Data/Control Flow

#### Flow 1: Gallery → Selection → Editing
1. User opens Foundry tab → `GalleryView` displayed
2. Gallery loads all mechanisms → creates `GalleryThumbnail` for each
3. Each thumbnail starts animation loop (30fps)
4. User clicks thumbnail → `clicked` signal emitted
5. `FoundryView` receives signal → transitions to editing mode
6. Editing mode shows parameter sliders + info panel + visualization

#### Flow 2: Motion Path Hover
1. User hovers over mechanism visualization
2. Hover event → `PathPreviewOverlay.show_path()`
3. Check `PathCache` for existing path
4. If miss: compute path by sampling mechanism at 360 angles
5. Cache result for future use
6. Draw path with dashed lines and point markers
7. Mouse leave → `hide_path()` clears overlay

#### Flow 3: Info Panel Update
1. User changes parameter slider
2. `FoundryView._on_parameter_changed()` called
3. Updates `current_parameters` dict
4. Calls `info_panel.update_content(mechanism_type, parameters)`
5. `ContentLoader` loads JSON content
6. Panel renders HTML with current parameter values highlighted
7. Display updated in ≤50ms

---

## 5. Detailed Design

### Feature 1: Motion Path Hover Preview

#### User Interaction
1. Toggle via toolbar: "🔍 Path Preview" (checkable action)
2. When enabled, hovering over mechanism shows trajectory
3. Path fades out after 2s of no interaction
4. Multiple points can be previewed (coupler, output, follower)

#### Visual Design
- Path: Dashed line, 2px width, semi-transparent cyan (#00CED1, alpha=0.6)
- Points: Small circles (4px), evenly spaced, lighter cyan (#E0FFFF, alpha=0.8)
- Direction arrows: Every 45° along path
- Label: "Path Preview (360° rotation)" at path start

#### Technical Implementation
```python
# In foundry_view.py
def _enable_path_preview(self):
    self.graphics_view.setMouseTracking(True)
    self.graphics_view.viewport().installEventFilter(self._path_filter)

def _on_hover_mechanism(self, pos: QPointF):
    if not self.path_preview_enabled:
        return
    
    # Identify hovered component (coupler, output, etc.)
    point_name = self._identify_hover_point(pos)
    if point_name:
        self.path_overlay.show_path(
            self.current_mechanism,
            self.current_parameters,
            point_name
        )
```

#### Path Computation Strategy
- Sample mechanism at 1° increments (360 samples)
- Compute position for target point at each angle
- Store as tuple of (x, y) coordinates
- Cache using (mechanism_type, params, point_name) as key
- Invalidate cache when parameters change beyond tolerance (±1%)

#### Performance Optimization
- Lazy computation: only compute path on first hover
- Coarse sampling: 360 points (sufficient visual smoothness)
- Adaptive quality: reduce to 180 points if computation >10ms
- LRU eviction: max 20 cached paths (~500KB each = 10MB total)

---

### Feature 2: Mechanism Gallery Landing Page

#### User Interaction
1. Foundry tab opens to gallery view (default)
2. Grid layout: 2x2 for 4 mechanisms (scalable to 3x3 for more)
3. Each thumbnail shows:
   - Animated mechanism preview (looping)
   - Display name below
   - Complexity badge (beginner/intermediate/advanced)
   - Tags (linkage, cam, gear)
4. Hover: thumbnail scales slightly (1.05x), border highlights
5. Click: transition to editing view with smooth fade
6. "Back to Gallery" button in editing view (top-left corner)

#### Visual Design
- **Thumbnail Size:** 300x250px (4:3 aspect ratio)
- **Grid Spacing:** 20px gap between thumbnails
- **Background:** Light gray (#F5F5F5)
- **Border:** 2px solid #CCC, hover → 3px solid #4A90E2
- **Animation:** 4s loop, 30fps
- **Complexity Badge:** Pill-shaped, top-right corner
  - Beginner: Green (#4CAF50)
  - Intermediate: Orange (#FF9800)
  - Advanced: Red (#F44336)

#### Thumbnail Animation Strategy
- **Static Snapshot Approach:**
  - Pre-render 4-6 keyframe angles (0°, 60°, 120°, 180°, 240°, 300°)
  - Interpolate between keyframes during animation
  - Pros: Fast, low CPU, smooth
  - Cons: Less accurate for complex motion
  
- **Live Animation Approach:** (Recommended)
  - Real-time rendering at 30fps (33ms budget)
  - Each thumbnail has independent QGraphicsScene
  - Mechanism compute + render per frame
  - Pros: Accurate, demonstrates real behavior
  - Cons: Higher CPU (acceptable for 4 mechanisms)

#### Grid Layout Logic
```python
class GalleryView(QWidget):
    def __init__(self):
        self._grid = QGridLayout()
        self._thumbnails: list[GalleryThumbnail] = []
        self._build_gallery()
    
    def _build_gallery(self):
        mechanisms = self.controller.list_mechanisms()
        for idx, item in enumerate(mechanisms):
            row = idx // 2
            col = idx % 2
            
            thumbnail = GalleryThumbnail(
                item.mechanism_type,
                item.display_name,
                PreviewConfig(
                    size=(300, 250),
                    fps=30,
                    loop_duration=4.0
                )
            )
            thumbnail.clicked.connect(self._on_thumbnail_clicked)
            self._grid.addWidget(thumbnail, row, col)
            self._thumbnails.append(thumbnail)
    
    def _on_thumbnail_clicked(self, mechanism_type: str):
        self.selection_changed.emit(mechanism_type)
```

#### Transition Animation
- Fade out gallery (300ms)
- Load editing view in background
- Fade in editing view (300ms)
- Total transition: 600ms

---

### Feature 3: Enhanced Educational Info Panel

#### Content Structure (JSON Schema)
```json
{
  "title": "Cam-Follower I",
  "goal": "Converts steady rotation into controlled up-and-down motion.",
  "parts": [
    "Cam (rotating lobe)",
    "Follower (vertical rod)",
    "Shaft (rotation axis)",
    "Pivot (follower guide)",
    "Base (mounting structure)"
  ],
  "advantages": [
    "Stable and predictable motion",
    "Flexible profile design",
    "Easy to vary follower length"
  ],
  "disadvantages": [
    "Contact wear over time",
    "Requires lubrication",
    "Limited to 2D motion"
  ],
  "materials": [
    "3D printing (PLA/ABS for cam)",
    "Laser cutting (acrylic for base)",
    "Metal rod (steel/aluminum for follower)"
  ],
  "cautions": [
    "Keep fingers clear of moving cam",
    "Ensure smooth rotation to avoid binding",
    "Check contact point for wear"
  ],
  "parameter_options": {
    "cam_radius": [
      {"value": 30.0, "label": "Small", "description": "Compact design"},
      {"value": 60.0, "label": "Medium", "description": "Balanced size"},
      {"value": 90.0, "label": "Large", "description": "Max displacement"}
    ],
    "follower_length": [
      {"value": 50.0, "label": "0.5 inch"},
      {"value": 100.0, "label": "1 inch"},
      {"value": 150.0, "label": "1.5 inch"}
    ]
  },
  "diagram_path": "diagrams/cam_follower_diagram.svg"
}
```

#### HTML Rendering Template
```html
<h2>{title}</h2>

<div class="goal">
  <b>Goal:</b> {goal}
</div>

<div class="diagram">
  <img src="{diagram_path}" alt="{title} Diagram" style="width:100%; max-width:300px;">
</div>

<h3>Adjustable Parameters</h3>
<ul>
  {for param in parameter_options}
    <li><b>{param.label}:</b>
      <select>{options}</select>
      <span class="current">(Current: {current_value})</span>
    </li>
  {endfor}
</ul>

<h3>Parts List</h3>
<ol>
  {for part in parts}
    <li>{part}</li>
  {endfor}
</ol>

<h3>Advantages</h3>
<ul>
  {for adv in advantages}
    <li>{adv}</li>
  {endfor}
</ul>

<h3>Disadvantages</h3>
<ul>
  {for disadv in disadvantages}
    <li>{disadv}</li>
  {endfor}
</ul>

<h3>Materials & Fabrication</h3>
<ul>
  {for material in materials}
    <li>{material}</li>
  {endfor}
</ul>

<h3>Cautions</h3>
<div class="cautions" style="color: #D32F2F; background: #FFEBEE; padding: 10px; border-radius: 4px;">
  <ul>
    {for caution in cautions}
      <li>{caution}</li>
    {endfor}
  </ul>
</div>
```

#### Discrete Parameter UI
For parameters with `parameter_options` in JSON:
- Render as button group (small/medium/large)
- Clicking button sets parameter to corresponding value
- Current selection highlighted with blue background
- Tooltip shows description on hover

---

## 6. Public API

### Path Cache API
```python
from automataii.application.mechanism_foundry import PathCache

cache = PathCache(max_size_mb=10)

# Compute and cache path
path = cache.compute_and_cache(
    mechanism=four_bar_mechanism,
    parameters={"ground_link": 150.0, ...},
    point_name="coupler_point",
    angle_samples=360
)

# Retrieve cached path
key = PathCacheKey(
    mechanism_type="four_bar",
    parameters=tuple(sorted(parameters.items())),
    point_name="coupler_point"
)
cached = cache.get(key)  # CachedPath | None

# Invalidate cache for mechanism
cache.invalidate("four_bar")
```

### Content Loader API
```python
from automataii.application.mechanism_foundry import ContentLoader

loader = ContentLoader()

# Load educational content
content = loader.load_content("cam_follower")

# Access content fields
print(content.title)  # "Cam-Follower I"
print(content.parts)  # ("Cam (rotating lobe)", ...)
print(content.advantages)  # ("Stable and predictable motion", ...)
```

### Gallery View API
```python
from automataii.ui.tabs.mechanism_foundry import GalleryView

gallery = GalleryView(controller)
gallery.selection_changed.connect(on_mechanism_selected)

# Programmatically select mechanism
gallery.select_mechanism("four_bar")

# Refresh thumbnails
gallery.refresh()
```

---

## 7. Dependencies

### Internal
- `src/automataii/ui/tabs/mechanism_foundry/foundry_view.py` (existing)
- `src/automataii/application/mechanism_foundry/controller.py` (existing)
- `src/automataii/mechanisms/core/protocols.py` (existing)
- `src/automataii/mechanisms/fourbar/compute.py` (existing)
- `src/automataii/mechanisms/cam/compute.py` (existing)

### External
- PyQt6 (QGraphicsScene, QGraphicsView, QTimer, QWidget)
- JSON (standard library, for content loading)
- Math (standard library, for path computation)

### New Dependencies (None)
- All features use existing dependencies

---

## 8. Test Strategy

### Unit Tests

#### Path Cache Tests
```python
def test_path_cache_hit():
    cache = PathCache(max_size_mb=1)
    mechanism = FourBarMechanism()
    params = {"ground_link": 150.0, ...}
    
    # First call: cache miss
    path1 = cache.compute_and_cache(mechanism, params, "coupler_point")
    
    # Second call: cache hit
    key = PathCacheKey(...)
    path2 = cache.get(key)
    
    assert path2 is not None
    assert path1.points == path2.points

def test_path_cache_invalidation():
    cache = PathCache()
    cache.compute_and_cache(...)
    cache.invalidate("four_bar")
    assert cache.get(key) is None

def test_path_cache_lru_eviction():
    cache = PathCache(max_size_mb=1)  # Small size
    # Fill cache beyond capacity
    # Verify oldest entries evicted
```

#### Content Loader Tests
```python
def test_load_content_valid():
    loader = ContentLoader()
    content = loader.load_content("cam_follower")
    assert content.title == "Cam-Follower I"
    assert len(content.parts) <= 5
    assert len(content.advantages) > 0

def test_load_content_missing():
    loader = ContentLoader()
    with pytest.raises(FileNotFoundError):
        loader.load_content("nonexistent")

def test_parameter_options_parsing():
    loader = ContentLoader()
    content = loader.load_content("cam_follower")
    options = content.parameter_options["cam_radius"]
    assert len(options) == 3
    assert options[0].label == "Small"
```

### Integration Tests

#### Gallery Rendering Test
```python
def test_gallery_loads_all_mechanisms(qtbot):
    controller = MechanismFoundryController()
    gallery = GalleryView(controller)
    qtbot.addWidget(gallery)
    
    # Verify all mechanisms have thumbnails
    assert len(gallery._thumbnails) == 4
    assert gallery._thumbnails[0].isVisible()

def test_thumbnail_animation_starts(qtbot):
    thumbnail = GalleryThumbnail("four_bar", "Four-Bar", ...)
    qtbot.addWidget(thumbnail)
    
    thumbnail.start_animation()
    assert thumbnail._animation_timer.isActive()
    
    thumbnail.stop_animation()
    assert not thumbnail._animation_timer.isActive()
```

#### Path Preview Integration Test
```python
def test_path_preview_displays_on_hover(qtbot):
    view = MechanismFoundryView()
    qtbot.addWidget(view)
    
    # Enable path preview
    view.path_preview_enabled = True
    
    # Simulate hover
    pos = QPointF(100, 100)
    view._on_hover_mechanism(pos)
    
    # Verify path visible
    assert view.path_overlay._visible
    assert len(view.path_overlay._path_items) > 0
```

### Performance Tests

#### Thumbnail Rendering Performance
```python
def test_thumbnail_render_performance():
    thumbnail = GalleryThumbnail("four_bar", "Four-Bar", ...)
    
    start = time.perf_counter()
    for _ in range(100):  # 100 frames
        thumbnail._render_frame()
    duration = time.perf_counter() - start
    
    avg_frame_time = duration / 100
    assert avg_frame_time < 0.033  # 30fps = 33ms per frame
```

#### Path Computation Performance
```python
def test_path_compute_performance():
    cache = PathCache()
    mechanism = FourBarMechanism()
    params = {"ground_link": 150.0, ...}
    
    start = time.perf_counter()
    path = cache.compute_and_cache(mechanism, params, "coupler_point", 360)
    duration = time.perf_counter() - start
    
    assert duration < 0.010  # 10ms budget
```

#### Gallery Load Performance
```python
def test_gallery_load_performance(qtbot):
    controller = MechanismFoundryController()
    
    start = time.perf_counter()
    gallery = GalleryView(controller)
    qtbot.addWidget(gallery)
    gallery.show()
    QApplication.processEvents()
    duration = time.perf_counter() - start
    
    assert duration < 0.500  # 500ms budget
```

### Regression Tests

#### Visual Regression for Thumbnails
```python
def test_thumbnail_visual_regression(qtbot):
    thumbnail = GalleryThumbnail("four_bar", "Four-Bar", ...)
    qtbot.addWidget(thumbnail)
    
    # Render at key angle
    thumbnail._current_angle = 45.0
    thumbnail._render_frame()
    
    # Capture screenshot
    pixmap = thumbnail.grab()
    
    # Compare to baseline
    baseline_path = Path("tests/baselines/four_bar_thumbnail_45deg.png")
    assert compare_images(pixmap, baseline_path, threshold=0.01)
```

---

## 9. Observability / Telemetry

### Telemetry Spans

#### Gallery Interactions
```python
telemetry_span(
    "foundry.gallery.load",
    mechanism_count=4,
    duration_ms=245,
    status="success"
)

telemetry_span(
    "foundry.gallery.thumbnail_clicked",
    mechanism_type="cam_follower",
    time_to_click_ms=1200  # Time from gallery open to click
)
```

#### Path Preview Usage
```python
telemetry_span(
    "foundry.path_preview.compute",
    mechanism_type="four_bar",
    point_name="coupler_point",
    angle_samples=360,
    duration_ms=8.2,
    cache_hit=False
)

telemetry_span(
    "foundry.path_preview.hover",
    mechanism_type="four_bar",
    cache_hit=True,
    display_duration_ms=2.1
)
```

#### Info Panel Updates
```python
telemetry_span(
    "foundry.info_panel.update",
    mechanism_type="cam_follower",
    content_size_bytes=2048,
    render_duration_ms=15,
    has_diagram=True
)
```

### Metrics Dashboard
- **Gallery Metrics:**
  - Gallery load time (p50/p95/p99)
  - Thumbnail render fps (min/avg/max)
  - Click-through rate per mechanism
  
- **Path Preview Metrics:**
  - Cache hit rate (%)
  - Path compute latency (p50/p95/p99)
  - Hover frequency (events per session)
  
- **Info Panel Metrics:**
  - Content load time (p50/p95/p99)
  - User scroll depth (% of content viewed)
  - Parameter option selection distribution

### Logging
- **INFO:** Gallery loaded, mechanism selected, path cached
- **WARNING:** Cache eviction, slow thumbnail render (>50ms), missing content
- **ERROR:** Content load failure, path compute exception, thumbnail crash

---

## 10. Performance / Resource Constraints

### Hard Constraints

#### Gallery
- **Load Time:** ≤500ms for 4 mechanisms
- **Thumbnail Render:** ≤33ms per frame (30fps)
- **Memory:** ≤20MB for gallery (5MB per thumbnail)
- **Transition:** ≤600ms (fade out + fade in)

#### Path Preview
- **Hover Response:** ≤50ms from hover to display
- **Path Compute:** ≤10ms (first time), ≤1ms (cached)
- **Cache Memory:** ≤10MB total (20 paths × 500KB)
- **Cache Hit Rate:** ≥95% after 5 minutes of use

#### Info Panel
- **Content Load:** ≤100ms per mechanism
- **Render Update:** ≤50ms on parameter change
- **Image Load:** ≤200ms per diagram
- **Memory:** ≤5MB per content (including images)

### Optimization Strategies

#### Gallery Optimization
1. **Lazy Thumbnail Creation:**
   - Create thumbnails only when scrolled into view
   - Pause animations for off-screen thumbnails
   
2. **Shared Renderer:**
   - Reuse single renderer instance across thumbnails
   - Only one scene per thumbnail (lightweight)
   
3. **Frame Skipping:**
   - If render >33ms, skip to next frame
   - Monitor fps and adapt quality dynamically

#### Path Preview Optimization
1. **Adaptive Sampling:**
   - Start with 180 samples (2° increments)
   - If compute <5ms, increase to 360 samples
   - Cache sampling level with path
   
2. **Spatial Indexing:**
   - Use grid to identify nearby cached paths
   - Reuse path if parameters within 5% tolerance
   
3. **Progressive Rendering:**
   - Display coarse path (90 points) immediately
   - Refine to full resolution over next 100ms

#### Info Panel Optimization
1. **Content Preloading:**
   - Load all JSON content at startup (4 files × 2KB = 8KB)
   - Lazy-load images only when mechanism selected
   
2. **HTML Caching:**
   - Cache rendered HTML for each mechanism
   - Invalidate only on parameter change
   
3. **Image Optimization:**
   - Use SVG diagrams (vector, small file size)
   - Compress to ≤50KB per diagram
   - Lazy-load images (not in initial HTML)

---

## 11. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|-----------|
| **Gallery thumbnails lag (CPU-bound)** | High | Medium | Use frame skipping, pause off-screen animations, profile and optimize hot paths |
| **Path cache memory explosion** | Medium | Low | LRU eviction, max 10MB limit, telemetry monitoring |
| **Educational content inaccurate/incomplete** | High | Medium | Technical review by ME expert, user testing, iterative refinement |
| **Info panel images missing/broken links** | Medium | Medium | Fallback to text-only mode, validate all paths at build time |
| **Transition animation janky** | Medium | High | Use Qt animation framework, test on low-end hardware, simplify if needed |
| **Path hover interferes with interaction** | Medium | Medium | Toggle button, clear path on click, timeout after 2s |
| **JSON schema evolves, breaks loader** | Low | Low | Versioning in JSON schema, validate on load, fail gracefully |
| **Mechanism count scales beyond 4** | Medium | Low | Implement scrolling, pagination, or search/filter |

---

## 12. Rollout / Rollback Plan

### Feature Flags
```python
# Per-feature flags
FOUNDRY_GALLERY_ENABLED = os.getenv("FOUNDRY_GALLERY_ENABLED", "false") == "true"
FOUNDRY_PATH_PREVIEW_ENABLED = os.getenv("FOUNDRY_PATH_PREVIEW_ENABLED", "false") == "true"
FOUNDRY_ENHANCED_INFO_ENABLED = os.getenv("FOUNDRY_ENHANCED_INFO_ENABLED", "false") == "true"

# Global flag (overrides individual when disabled)
FOUNDRY_ENHANCEMENTS_ENABLED = os.getenv("FOUNDRY_ENHANCEMENTS_ENABLED", "false") == "true"
```

### Phased Rollout

#### Phase 1: Path Preview (Week 1-2)
**Goal:** Add hover preview without UI changes
- Implement `PathCache` and `PathPreviewOverlay`
- Add toggle button to toolbar (default: off)
- Test with all 4 mechanism types
- Validate performance (cache hit rate, latency)
- **Feature flag:** `FOUNDRY_PATH_PREVIEW_ENABLED=true`

#### Phase 2: Enhanced Info Panel (Week 3-4)
**Goal:** Upgrade info panel with educational content
- Create JSON content files for 4 mechanisms
- Implement `ContentLoader` and `EducationalInfoPanel`
- Generate/create SVG diagrams
- Replace existing info panel (backward compatible)
- **Feature flag:** `FOUNDRY_ENHANCED_INFO_ENABLED=true`

#### Phase 3: Gallery View (Week 5-6)
**Goal:** Add visual catalog landing page
- Implement `GalleryView` and `GalleryThumbnail`
- Create transition animation
- Add "Back to Gallery" button
- Test thumbnail performance (4 simultaneous animations)
- **Feature flag:** `FOUNDRY_GALLERY_ENABLED=true`

#### Phase 4: Integration & Polish (Week 7)
**Goal:** Combine all features, refine UX
- Enable all features together
- User testing session (5 users)
- Fix issues discovered in testing
- Performance optimization pass
- Documentation updates

#### Phase 5: Production Rollout (Week 8)
- **Day 1-2:** Internal testing (dev team)
- **Day 3-4:** Alpha users (10% rollout)
- **Day 5-6:** Beta users (50% rollout)
- **Day 7:** Full rollout (100%)
- **Week 9:** Remove feature flags (default: enabled)

### Rollback Procedure
1. **Immediate:** Flip feature flag to `false`
2. **Quick:** Revert to previous UI (dropdown selection, basic info panel)
3. **Gradual:** Fix issues, re-enable features one by one

---

## 13. Definition of Done (DoD)

### Per-Feature DoD

#### Path Preview DoD
- [ ] `PathCache` implemented with LRU eviction
- [ ] `PathPreviewOverlay` displays paths on hover
- [ ] Toolbar toggle button functional
- [ ] Tested with all 4 mechanism types
- [ ] Performance within budget (≤50ms hover response)
- [ ] Cache hit rate ≥95% after 5 minutes
- [ ] Unit tests passing (≥85% coverage)
- [ ] Telemetry integrated
- [ ] Documentation updated

#### Enhanced Info Panel DoD
- [ ] JSON content created for 4 mechanisms
- [ ] `ContentLoader` implemented
- [ ] `EducationalInfoPanel` renders HTML
- [ ] SVG diagrams created (4 mechanisms)
- [ ] Discrete parameter options functional
- [ ] Content reviewed by ME expert
- [ ] Performance within budget (≤50ms update)
- [ ] Unit tests passing (≥85% coverage)
- [ ] Telemetry integrated
- [ ] Documentation updated

#### Gallery View DoD
- [ ] `GalleryView` displays 2x2 grid
- [ ] `GalleryThumbnail` animates smoothly (30fps)
- [ ] Click → transition to editing view
- [ ] "Back to Gallery" button functional
- [ ] Thumbnail performance within budget (≤33ms/frame)
- [ ] Gallery load time ≤500ms
- [ ] Visual regression tests passing
- [ ] Unit tests passing (≥85% coverage)
- [ ] Telemetry integrated
- [ ] Documentation updated

### Final Project DoD
- [ ] All 3 features implemented and integrated
- [ ] Zero regressions in existing Foundry functionality
- [ ] Performance metrics within targets (gallery load, hover response, render fps)
- [ ] User testing completed (5 users, positive feedback)
- [ ] Educational content reviewed and accurate
- [ ] Test coverage ≥85% for new modules
- [ ] Telemetry spans emitting for all features
- [ ] Feature flags removed (enabled by default)
- [ ] Documentation complete:
  - [ ] PRD (this document)
  - [ ] User guide for new features
  - [ ] Technical README for new modules
  - [ ] ADR documenting design decisions
- [ ] Code review approved
- [ ] CI/CD pipeline passing

---

## 14. Success Criteria

### Must-Have (P0)
1. ✅ Gallery loads in ≤500ms
2. ✅ Thumbnails animate smoothly (≥25fps)
3. ✅ Path preview responds in ≤50ms
4. ✅ Info panel displays all required sections
5. ✅ Zero regressions in existing features

### Should-Have (P1)
1. ✅ Educational content reviewed by expert
2. ✅ Cache hit rate ≥95%
3. ✅ User testing shows improved discovery time
4. ✅ Diagrams render correctly
5. ✅ Discrete parameter options functional

### Nice-to-Have (P2)
1. Gallery search/filter functionality
2. Thumbnail hover shows mechanism stats
3. Path preview with velocity vectors
4. Export educational content to PDF
5. Animated diagrams in info panel

---

## 15. Open Questions

1. **Should gallery be default landing page or opt-in?**
   - Option A: Gallery is default (user-friendly, visual)
   - Option B: Dropdown is default (familiar, faster for power users)
   - **Recommendation:** Gallery default, with keyboard shortcut (Ctrl+G) to toggle

2. **How to handle mechanism count scaling beyond 4?**
   - Option A: Scrollable grid (simple, works for any count)
   - Option B: Pagination (cleaner, but extra clicks)
   - **Recommendation:** Scrollable grid initially, pagination if >12 mechanisms

3. **Should path preview be enabled by default?**
   - Option A: Enabled by default (discoverable, educational)
   - Option B: Disabled by default (cleaner, user opts in)
   - **Recommendation:** Disabled by default, tooltip on toolbar to encourage exploration

4. **Where to store educational content: JSON vs. database?**
   - Option A: JSON files (simple, versionable, no DB dependency)
   - Option B: SQLite database (queryable, better for large catalogs)
   - **Recommendation:** JSON files for now (4-10 mechanisms), migrate to DB if >50 mechanisms

5. **Should discrete parameter options replace sliders or augment them?**
   - Option A: Replace sliders (simpler UI, less control)
   - Option B: Augment sliders (more flexibility, but cluttered)
   - **Recommendation:** Augment sliders—buttons set value, slider fine-tunes

---

## 16. Next Steps

### Immediate Actions
1. **Get approval** on this PRD from stakeholders
2. **Create Phase 1 implementation plan** (Path Preview, detailed task breakdown)
3. **Set up telemetry baseline** (capture current Foundry usage metrics)
4. **Draft educational content** for 1-2 mechanisms (get expert review)
5. **Create SVG diagram template** for mechanism visualization

### First Implementation Task
**Path Preview (Phase 1, Week 1):**
1. Create `path_cache.py` with `PathCache` class
2. Add unit tests for cache operations
3. Create `path_preview.py` with `PathPreviewOverlay` class
4. Integrate overlay into `foundry_view.py`
5. Add toolbar toggle button
6. Test with four-bar mechanism
7. Validate performance (latency, cache hit rate)

---

## Appendix A: JSON Content Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "MechanismContent",
  "type": "object",
  "required": ["title", "goal", "parts", "advantages", "disadvantages", "materials", "cautions"],
  "properties": {
    "title": {
      "type": "string",
      "description": "Mechanism name with variant identifier"
    },
    "goal": {
      "type": "string",
      "description": "1-2 sentence description of mechanism purpose"
    },
    "parts": {
      "type": "array",
      "items": {"type": "string"},
      "maxItems": 5,
      "description": "Key components of mechanism"
    },
    "advantages": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Benefits and strengths"
    },
    "disadvantages": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Limitations and weaknesses"
    },
    "materials": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Fabrication suggestions"
    },
    "cautions": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Safety and operational warnings"
    },
    "parameter_options": {
      "type": "object",
      "description": "Discrete options for parameters",
      "additionalProperties": {
        "type": "array",
        "items": {
          "type": "object",
          "required": ["value", "label"],
          "properties": {
            "value": {"type": "number"},
            "label": {"type": "string"},
            "description": {"type": "string"}
          }
        }
      }
    },
    "diagram_path": {
      "type": "string",
      "description": "Relative path to SVG diagram"
    }
  }
}
```

---

## Appendix B: Example Content File

**File:** `resources/mechanism_content/cam_follower.json`

```json
{
  "title": "Cam-Follower I",
  "goal": "Converts steady rotation into controlled up-and-down motion using a shaped cam profile.",
  "parts": [
    "Cam (rotating lobe with egg-shaped profile)",
    "Follower (vertical rod that rides on cam)",
    "Shaft (rotation axis for cam)",
    "Guide (keeps follower aligned)",
    "Base (mounting structure)"
  ],
  "advantages": [
    "Stable and predictable motion path",
    "Flexible profile design enables custom motion curves",
    "Easy to vary follower length for different applications",
    "Simple to manufacture with 3D printing or CNC"
  ],
  "disadvantages": [
    "Contact wear occurs over time at cam-follower interface",
    "Requires lubrication to reduce friction",
    "Limited to 2D motion (vertical displacement only)",
    "High-speed operation can cause vibration"
  ],
  "materials": [
    "3D printing: PLA or ABS plastic for cam body",
    "Laser cutting: Acrylic or wood for base plate",
    "Metal rod: Steel or aluminum for follower shaft",
    "Bearings: Ball bearings for smooth rotation"
  ],
  "cautions": [
    "Keep fingers clear of moving cam during operation",
    "Ensure smooth rotation to avoid binding or jamming",
    "Check contact point periodically for wear",
    "Use proper lubrication to extend mechanism life"
  ],
  "parameter_options": {
    "cam_radius": [
      {"value": 30.0, "label": "Small", "description": "Compact design, 30mm radius"},
      {"value": 60.0, "label": "Medium", "description": "Balanced size, 60mm radius"},
      {"value": 90.0, "label": "Large", "description": "Maximum displacement, 90mm radius"}
    ],
    "follower_length": [
      {"value": 50.0, "label": "0.5 inch (12.7mm)"},
      {"value": 100.0, "label": "1 inch (25.4mm)"},
      {"value": 150.0, "label": "1.5 inch (38.1mm)"}
    ]
  },
  "diagram_path": "diagrams/cam_follower_diagram.svg"
}
```

---

**End of PRD**
