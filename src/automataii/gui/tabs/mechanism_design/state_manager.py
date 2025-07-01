# mechanism_design/state_manager.py

from PyQt6.QtCore import QObject, pyqtSignal

class MechanismStateManager(QObject):
    """
    (Model) 메커니즘 탭의 모든 상태를 중앙에서 관리합니다.
    - 파트, 경로, 메커니즘 데이터 저장
    - 선택 상태, 활성화 상태 등 UI 상태 관리
    - 상태 변경 시 구체적인 시그널을 발생시켜 다른 컴포넌트에 알림
    """
    state_changed = pyqtSignal()
    mechanism_added = pyqtSignal(str)
    mechanisms_cleared = pyqtSignal()
    mechanism_layer_updated = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.path_data = {}
        self.parts_data = {}
        self.part_enabled_state = {}
        self.mechanism_layers = {}
        self.mechanism_enabled_state = {}
        self.selected_part_name = None
        self.initial_skeleton_data = None

    def update_path_data(self, path_data):
        self.path_data = path_data.copy() if path_data else {}
        for name in self.path_data:
            if name not in self.part_enabled_state:
                self.part_enabled_state[name] = True
        self.state_changed.emit()

    def update_parts_data(self, parts_data):
        self.parts_data = parts_data.copy() if parts_data else {}
        self.state_changed.emit()

    def cache_initial_skeleton(self, skeleton_data):
        self.initial_skeleton_data = skeleton_data.copy() if skeleton_data else None
        self.state_changed.emit()

    def set_selected_part(self, part_name):
        if self.selected_part_name != part_name:
            self.selected_part_name = part_name
            self.state_changed.emit()

    def toggle_part_enabled(self, part_name):
        if part_name in self.path_data:
            current = self.part_enabled_state.get(part_name, True)
            self.part_enabled_state[part_name] = not current
            self.state_changed.emit()

    def add_mechanism(self, mechanism_id, layer_data):
        self.mechanism_layers[mechanism_id] = layer_data
        self.mechanism_enabled_state[mechanism_id] = True
        self.mechanism_added.emit(mechanism_id)
        self.state_changed.emit()

    def clear_mechanisms_for_part(self, part_name):
        ids_to_remove = [mid for mid, data in self.mechanism_layers.items() if data.get("part_name") == part_name]
        if not ids_to_remove:
            return
        for mid in ids_to_remove:
            del self.mechanism_layers[mid]
            if mid in self.mechanism_enabled_state:
                del self.mechanism_enabled_state[mid]
        self.mechanisms_cleared.emit()
        self.state_changed.emit()

    def toggle_mechanism_enabled(self, mechanism_id: str):
        """Toggles the enabled state of a single mechanism."""
        if mechanism_id in self.mechanism_enabled_state:
            self.mechanism_enabled_state[mechanism_id] = not self.mechanism_enabled_state[mechanism_id]
            self.state_changed.emit()

    def update_mechanism_parameters(self, mechanism_id, params_update):
        """Updates the parameters for a specific mechanism by merging the changes."""
        if mechanism_id in self.mechanism_layers:
            if "params" not in self.mechanism_layers[mechanism_id]:
                self.mechanism_layers[mechanism_id]["params"] = {}
            self.mechanism_layers[mechanism_id]["params"].update(params_update)
            self.mechanism_layer_updated.emit(mechanism_id)
            # No need to emit state_changed here, as layer_updated is more specific

    def update_mechanism_layer(self, mechanism_id, layer_data):
        """Replaces the entire layer data for a mechanism, used for undo/redo."""
        if mechanism_id in self.mechanism_layers:
            self.mechanism_layers[mechanism_id] = layer_data
            self.mechanism_layer_updated.emit(mechanism_id)
            self.state_changed.emit() # Full state change for UI update

    def clear_all(self):
        """Clears all data from the state manager."""
        self.path_data.clear()
        self.parts_data.clear()
        self.part_enabled_state.clear()
        self.mechanism_layers.clear()
        self.mechanism_enabled_state.clear()
        self.selected_part_name = None
        self.mechanisms_cleared.emit()
        self.state_changed.emit()
