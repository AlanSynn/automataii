# CAM Mechanism Decoupling Analysis

## Current Data Flow and Coupling Issues

### 1. Data Sources and Flow

```
JSON Data (generated_mechanism_paths.json)
    ↓
Recommendation Dialog (recommendation_dialog.py)
    ↓
_handle_recommendation_selection (mechanism_design_tab.py:1680)
    ↓
_create_cam_visuals (mechanism_design_tab.py:4915)
    ↓
Scene Display
```

### 2. Current Coupling Points

#### A. **JSON Data Level**
- Location: `src/automataii/kinematics/generated_mechanism_paths.json`
- Fixed values: `base_radius: 25.0`, `eccentricity: 10.0`
- Issue: Hard-coded values don't consider character size

#### B. **Handler Level** 
- Location: `_handle_recommendation_selection` (line 1680)
- Current: Passes parameters directly from JSON
- Coupling: Line 1707 - `"params": mechanism_data.get("parameters", {})`
- Scaling added: Lines 1741-1743 (but fixed values)

#### C. **Visual Creation Level**
- Location: `_create_cam_visuals` (line 4915)
- Scaling applied: Lines 4931-4932
- Issue: Fixed scaling factors (0.15, 1.5) regardless of character size

### 3. Identified Decoupling Points

#### **Point 1: Character-Relative Scaling (MISSING)**
```python
# Need to add at _handle_recommendation_selection
character_height = self.get_character_height()  # Not implemented
relative_scale = character_height / 500.0  # Assuming 500px standard height
```

#### **Point 2: Transform Function Creation**
- Location: `_get_scene_transform_function` (line 2007)
- Issue: Fallback position is fixed (line 4982)
- Need: Dynamic positioning based on character anchor point

#### **Point 3: Parameter Scaling**
- Currently at: `_create_cam_visuals` (lines 4931-4932)
- Should be at: `_handle_recommendation_selection` before creating layer_data

## Proposed Decoupling Solution

### Step 1: Add Character Context
```python
def _get_character_context(self):
    """Get character size and position for relative scaling."""
    # Get skeleton bounds
    # Calculate appropriate scale
    # Return context dict
```

### Step 2: Scale at Data Entry Point
```python
def _handle_recommendation_selection(self, mechanism_data):
    # Get character context FIRST
    char_context = self._get_character_context()
    
    # Scale parameters based on character
    if internal_type == "cam":
        params = mechanism_data.get("parameters", {})
        scaled_params = self._scale_cam_params(params, char_context)
        graphics_data["params"] = scaled_params
```

### Step 3: Remove Fixed Scaling from Visuals
```python
def _create_cam_visuals(self, mechanism_data):
    # Use pre-scaled parameters
    # No fixed scaling factors here
    base_radius = params.get("base_radius")  # Already scaled
    eccentricity = params.get("eccentricity")  # Already scaled
```

## Current Fixed Values to Remove

1. **_create_cam_visuals** (line 4931-4932):
   - `cam_scale_factor = 0.15` → Should be character-relative
   - `rod_length_multiplier = 1.5` → Should be proportional

2. **_handle_recommendation_selection** (line 1742-1743):
   - Fixed scaling factors → Should calculate based on character

3. **Animation** (line 2791-2792):
   - Fixed default values → Should get from layer_data

4. **Parametric Handles** (line 7187-7188):
   - Fixed defaults → Should get from layer_data

## Implementation Priority

### High Priority (Immediate)
1. Calculate character-relative scaling
2. Apply scaling at recommendation handler level
3. Ensure CAM is positioned below character

### Medium Priority
1. Dynamic transform function based on character position
2. Remove all fixed scaling factors
3. Add character size detection

### Low Priority
1. Store scaling context in mechanism data
2. Add UI for manual scale adjustment
3. Preview scaling before applying

## Testing Requirements

1. Test with different character sizes
2. Verify CAM is always below character
3. Check egg shape is maintained
4. Ensure animation uses correct scaling
5. Verify parametric editing maintains proportions

## Notes

- The main issue is that scaling is applied at the visual creation level rather than at data entry
- Character context is not considered anywhere in the current flow
- Transform functions are created multiple times with different parameters
- Need centralized scaling calculation based on character dimensions