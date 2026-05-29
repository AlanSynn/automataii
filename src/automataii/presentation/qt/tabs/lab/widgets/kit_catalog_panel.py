"""Kit asset list panel for Lab."""

from __future__ import annotations

from collections.abc import Sequence

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from automataii.application.ms4n import KitAssetViewModel


class KitCatalogPanel(QWidget):
    asset_selected = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("lab_kit_catalog_panel")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Lab kit assets"))
        self.asset_list = QListWidget(self)
        self.asset_list.itemSelectionChanged.connect(self._emit_selected_asset)
        layout.addWidget(self.asset_list)

    def set_assets(self, assets: Sequence[KitAssetViewModel]) -> None:
        self.asset_list.clear()
        for asset in assets:
            item = QListWidgetItem(asset.label)
            item.setData(256, asset.asset_id)
            item.setToolTip(asset.description)
            self.asset_list.addItem(item)

    def _emit_selected_asset(self) -> None:
        item = self.asset_list.currentItem()
        if item is not None:
            self.asset_selected.emit(str(item.data(256)))
