"""
Layout utilities for safely managing Qt layouts.

This module provides utilities for common layout operations like
clearing layouts and removing widgets, handling Qt's ownership model.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QLayout, QWidget


def clear_layout(layout: QLayout | None, delete_widgets: bool = True) -> None:
    """Clear all items from a layout safely.

    Removes all widgets and sub-layouts from the given layout.
    Handles Qt's ownership model correctly to prevent memory leaks
    and access violations.

    Args:
        layout: The layout to clear. If None, does nothing.
        delete_widgets: If True, delete widgets. If False, just remove from layout.

    Example:
        from automataii.presentation.qt.shared import clear_layout

        # Clear a layout completely
        clear_layout(self.my_layout)

        # Clear but keep widgets for reuse
        clear_layout(self.my_layout, delete_widgets=False)
    """
    if layout is None:
        return

    while layout.count():
        child = layout.takeAt(0)
        if child is None:
            continue

        # Handle nested layouts recursively
        if child.layout():
            clear_layout(child.layout(), delete_widgets)

        # Handle widgets
        widget = child.widget()
        if widget is not None:
            if delete_widgets:
                widget.setParent(None)
                widget.deleteLater()
            else:
                widget.setParent(None)


def remove_widget_from_layout(
    layout: QLayout | None,
    widget: QWidget,
    delete_widget: bool = True
) -> bool:
    """Remove a specific widget from a layout.

    Searches the layout for the widget and removes it if found.

    Args:
        layout: The layout to search
        widget: The widget to remove
        delete_widget: If True, schedule the widget for deletion

    Returns:
        True if widget was found and removed, False otherwise

    Example:
        from automataii.presentation.qt.shared import remove_widget_from_layout

        if remove_widget_from_layout(self.main_layout, self.old_button):
            print("Button removed successfully")
    """
    if layout is None or widget is None:
        return False

    for i in range(layout.count()):
        item = layout.itemAt(i)
        if item is None:
            continue

        if item.widget() is widget:
            layout.takeAt(i)
            if delete_widget:
                widget.setParent(None)
                widget.deleteLater()
            else:
                widget.setParent(None)
            return True

        # Check nested layouts
        if item.layout():
            if remove_widget_from_layout(item.layout(), widget, delete_widget):
                return True

    return False


def replace_widget_in_layout(
    layout: QLayout | None,
    old_widget: QWidget,
    new_widget: QWidget,
    delete_old: bool = True
) -> bool:
    """Replace a widget in a layout with another widget.

    Maintains the position of the widget in the layout.

    Args:
        layout: The layout containing the widget
        old_widget: The widget to replace
        new_widget: The widget to insert
        delete_old: If True, schedule the old widget for deletion

    Returns:
        True if replacement successful, False otherwise

    Example:
        from automataii.presentation.qt.shared import replace_widget_in_layout

        replace_widget_in_layout(
            self.toolbar_layout,
            self.old_button,
            self.new_button
        )
    """
    if layout is None or old_widget is None or new_widget is None:
        return False

    for i in range(layout.count()):
        item = layout.itemAt(i)
        if item is None:
            continue

        if item.widget() is old_widget:
            layout.takeAt(i)
            layout.insertWidget(i, new_widget)

            if delete_old:
                old_widget.setParent(None)
                old_widget.deleteLater()
            else:
                old_widget.setParent(None)

            return True

    return False
