"""
Interactive Tutorial System for Mechanism Dictionary Tab.
Provides guided learning with step-by-step instructions and visual overlays.
"""

import logging
from typing import List, Dict, Any, Optional, Callable
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve, QRect
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPixmap
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QFrame, QGraphicsView, QGraphicsScene, QGraphicsItem,
    QGraphicsRectItem, QGraphicsTextItem, QGraphicsEllipseItem,
    QApplication
)

from .styling import ModernStyling

logger = logging.getLogger(__name__)


class TutorialStep:
    """Represents a single step in a tutorial sequence."""
    
    def __init__(self, 
                 title: str,
                 description: str,
                 target_element: str = None,
                 highlight_area: QRect = None,
                 action_required: str = None,
                 validation_func: Callable = None):
        self.title = title
        self.description = description
        self.target_element = target_element  # CSS selector or widget name
        self.highlight_area = highlight_area  # Area to highlight
        self.action_required = action_required  # "click", "drag", "observe", etc.
        self.validation_func = validation_func  # Function to check if step completed
        self.completed = False


class TutorialOverlay(QWidget):
    """Semi-transparent overlay that highlights tutorial elements."""
    
    step_completed = pyqtSignal()
    tutorial_skipped = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 0.7);")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        
        # Tutorial content
        self.current_step: Optional[TutorialStep] = None
        self.highlight_rect = QRect()
        
        # Setup UI
        self._setup_ui()
        
        # Animation for highlighting
        self.pulse_animation = QPropertyAnimation(self, b"geometry")
        self.pulse_animation.setDuration(1000)
        self.pulse_animation.setLoopCount(-1)  # Infinite loop
        
    def _setup_ui(self):
        """Setup tutorial overlay UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Tutorial card
        self.tutorial_card = QFrame()
        self.tutorial_card.setFixedSize(400, 200)
        self.tutorial_card.setStyleSheet(f"""
            QFrame {{
                background-color: {ModernStyling.COLORS['surface']};
                border-radius: 12px;
                border: 1px solid {ModernStyling.COLORS['outline']};
            }}
        """)
        
        card_layout = QVBoxLayout(self.tutorial_card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        self.title_label = QLabel("Tutorial Step")
        self.title_label.setFont(QFont(ModernStyling.TYPOGRAPHY['font_family'], 
                                     ModernStyling.TYPOGRAPHY['font_size_h2'], QFont.Weight.Bold))
        self.title_label.setStyleSheet(f"color: {ModernStyling.COLORS['primary']};")
        card_layout.addWidget(self.title_label)
        
        # Description
        self.description_label = QLabel("Follow the instructions to learn about mechanisms.")
        self.description_label.setWordWrap(True)
        self.description_label.setStyleSheet(f"""
            color: {ModernStyling.COLORS['on_surface']};
            font-size: {ModernStyling.TYPOGRAPHY['font_size_body']}px;
            line-height: 1.4;
        """)
        card_layout.addWidget(self.description_label)
        
        card_layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.skip_button = QPushButton("Skip Tutorial")
        self.skip_button.setStyleSheet(ModernStyling.get_button_style("secondary"))
        self.skip_button.clicked.connect(self.tutorial_skipped.emit)
        button_layout.addWidget(self.skip_button)
        
        button_layout.addStretch()
        
        self.next_button = QPushButton("Next")
        self.next_button.setStyleSheet(ModernStyling.get_button_style("primary"))
        self.next_button.clicked.connect(self.step_completed.emit)
        button_layout.addWidget(self.next_button)
        
        card_layout.addLayout(button_layout)
        
        # Position card in center-top
        layout.addWidget(self.tutorial_card, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch()
    
    def show_step(self, step: TutorialStep):
        """Display a tutorial step."""
        self.current_step = step
        
        # Update content
        self.title_label.setText(step.title)
        self.description_label.setText(step.description)
        
        # Update button text based on action required
        if step.action_required:
            if step.action_required == "observe":
                self.next_button.setText("I See It")
            elif step.action_required == "drag":
                self.next_button.setText("Try Dragging")
            elif step.action_required == "click":
                self.next_button.setText("Click It")
            else:
                self.next_button.setText("Next")
        else:
            self.next_button.setText("Continue")
        
        # Setup highlight area if provided
        if step.highlight_area:
            self.highlight_rect = step.highlight_area
            self.start_pulse_animation()
        
        self.show()
        self.raise_()
    
    def start_pulse_animation(self):
        """Start pulsing animation for highlighted area."""
        if not self.highlight_rect.isValid():
            return
        
        # Create pulsing effect by varying the highlight size
        self.pulse_animation.setStartValue(self.highlight_rect)
        expanded_rect = self.highlight_rect.adjusted(-10, -10, 10, 10)
        self.pulse_animation.setEndValue(expanded_rect)
        self.pulse_animation.start()
    
    def paintEvent(self, event):
        """Paint the overlay with highlight area."""
        super().paintEvent(event)
        
        if not self.highlight_rect.isValid():
            return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw highlight border
        highlight_pen = QPen(QColor(ModernStyling.COLORS['primary']), 3, Qt.PenStyle.DashLine)
        painter.setPen(highlight_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(self.highlight_rect, 8, 8)
        
        # Draw arrow pointing to highlight
        self._draw_arrow_to_highlight(painter)
    
    def _draw_arrow_to_highlight(self, painter: QPainter):
        """Draw an arrow pointing to the highlighted area."""
        if not self.highlight_rect.isValid():
            return
        
        # Calculate arrow position
        card_center = self.tutorial_card.geometry().center()
        highlight_center = self.highlight_rect.center()
        
        # Draw arrow from card to highlight
        painter.setPen(QPen(QColor(ModernStyling.COLORS['primary']), 2))
        painter.drawLine(card_center, highlight_center)
        
        # Draw arrowhead
        # (Simplified arrow implementation)


class TutorialManager(QWidget):
    """Manages tutorial sequences and coordinates with the main interface."""
    
    tutorial_completed = pyqtSignal(str)  # tutorial_name
    tutorial_skipped = pyqtSignal(str)    # tutorial_name
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_tutorial: Optional[str] = None
        self.current_step_index = 0
        self.tutorial_steps: List[TutorialStep] = []
        
        # Tutorial overlay
        self.overlay = TutorialOverlay(self)
        self.overlay.step_completed.connect(self._next_step)
        self.overlay.tutorial_skipped.connect(self._skip_tutorial)
        self.overlay.hide()
        
        # Define tutorial sequences
        self._define_tutorials()
    
    def _define_tutorials(self):
        """Define all available tutorial sequences."""
        self.tutorials = {
            "first_visit": [
                TutorialStep(
                    title="Welcome to Mechanism Dictionary! 👋",
                    description="This interactive tool helps you learn about mechanical engineering concepts. Let's start with a quick tour!",
                    action_required="observe"
                ),
                TutorialStep(
                    title="Mechanism Library",
                    description="The left sidebar shows different types of mechanisms. Each card displays the mechanism's complexity level and main application.",
                    target_element="sidebar",
                    action_required="observe"
                ),
                TutorialStep(
                    title="Interactive Playground",
                    description="The center area is where you can see and interact with mechanisms. Look for blue circles - these are drag handles you can move!",
                    target_element="playground",
                    action_required="observe"
                ),
                TutorialStep(
                    title="Analysis Panel",
                    description="The right panel shows detailed analysis and controls. This updates in real-time as you modify mechanisms.",
                    target_element="inspector",
                    action_required="observe"
                ),
                TutorialStep(
                    title="Ready to Start!",
                    description="Click on any mechanism in the sidebar to begin exploring. Don't forget to try dragging the blue handles!",
                    action_required="click"
                )
            ],
            
            "four_bar_basics": [
                TutorialStep(
                    title="Four-Bar Linkage Basics",
                    description="A four-bar linkage consists of four rigid links connected by joints. Let's explore how changing link lengths affects motion.",
                    action_required="observe"
                ),
                TutorialStep(
                    title="Drag Handles",
                    description="The blue circles are drag handles. Try dragging one to change the link length. Watch how the mechanism's motion changes!",
                    action_required="drag"
                ),
                TutorialStep(
                    title="Grashof's Law",
                    description="Look at the analysis panel. Grashof's Law determines what type of motion the linkage can produce. Try making different configurations!",
                    action_required="observe"
                ),
                TutorialStep(
                    title="Path Tracing",
                    description="Press play to see the path traced by the end point. This helps visualize the mechanism's workspace.",
                    action_required="click"
                )
            ],
            
            "cam_mechanism": [
                TutorialStep(
                    title="Cam and Follower",
                    description="Cam mechanisms convert rotary motion to oscillating motion. The cam profile determines the follower's motion pattern.",
                    action_required="observe"
                ),
                TutorialStep(
                    title="Adjust Cam Parameters",
                    description="Try changing the base radius and lift height using the drag handles. Notice how this affects the motion profile.",
                    action_required="drag"
                ),
                TutorialStep(
                    title="Pressure Angle",
                    description="The pressure angle affects force transmission efficiency. Watch how it changes as you modify the follower offset.",
                    action_required="observe"
                )
            ]
        }
    
    def start_tutorial(self, tutorial_name: str):
        """Start a specific tutorial sequence."""
        if tutorial_name not in self.tutorials:
            logger.error(f"Tutorial '{tutorial_name}' not found")
            return
        
        self.current_tutorial = tutorial_name
        self.tutorial_steps = self.tutorials[tutorial_name]
        self.current_step_index = 0
        
        # Show first step
        self._show_current_step()
        
        logger.info(f"Started tutorial: {tutorial_name}")
    
    def _show_current_step(self):
        """Display the current tutorial step."""
        if self.current_step_index >= len(self.tutorial_steps):
            self._complete_tutorial()
            return
        
        current_step = self.tutorial_steps[self.current_step_index]
        
        # Calculate highlight area if target element specified
        if current_step.target_element:
            highlight_rect = self._get_element_rect(current_step.target_element)
            current_step.highlight_area = highlight_rect
        
        self.overlay.show_step(current_step)
    
    def _get_element_rect(self, element_name: str) -> QRect:
        """Get the screen rectangle for a UI element."""
        # This would need to be implemented based on the actual UI structure
        # For now, return a placeholder rectangle
        if element_name == "sidebar":
            return QRect(0, 0, 320, 600)
        elif element_name == "playground":
            return QRect(320, 0, 800, 600)
        elif element_name == "inspector":
            return QRect(1120, 0, 320, 600)
        else:
            return QRect(100, 100, 200, 100)  # Default highlight
    
    def _next_step(self):
        """Advance to the next tutorial step."""
        self.current_step_index += 1
        self._show_current_step()
    
    def _skip_tutorial(self):
        """Skip the current tutorial."""
        self.overlay.hide()
        if self.current_tutorial:
            self.tutorial_skipped.emit(self.current_tutorial)
        self.current_tutorial = None
    
    def _complete_tutorial(self):
        """Complete the current tutorial."""
        self.overlay.hide()
        if self.current_tutorial:
            self.tutorial_completed.emit(self.current_tutorial)
            logger.info(f"Completed tutorial: {self.current_tutorial}")
        self.current_tutorial = None
    
    def resizeEvent(self, event):
        """Resize overlay to match parent."""
        super().resizeEvent(event)
        if self.overlay:
            self.overlay.resize(self.size())


class LearningPathManager:
    """Manages progressive learning paths and prerequisites."""
    
    def __init__(self):
        self.completed_tutorials = set()
        self.user_progress = {
            "mechanisms_viewed": set(),
            "concepts_learned": set(),
            "skill_level": "beginner"  # beginner, intermediate, advanced
        }
        
        # Define learning prerequisites
        self.prerequisites = {
            "cam_mechanism": ["four_bar_basics"],
            "geneva_drive": ["four_bar_basics", "gear_systems"],
            "six_bar_linkage": ["four_bar_basics"]
        }
    
    def can_access_tutorial(self, tutorial_name: str) -> bool:
        """Check if user has prerequisites for a tutorial."""
        if tutorial_name not in self.prerequisites:
            return True  # No prerequisites
        
        required = set(self.prerequisites[tutorial_name])
        completed = set(self.completed_tutorials)
        
        return required.issubset(completed)
    
    def complete_tutorial(self, tutorial_name: str):
        """Mark a tutorial as completed."""
        self.completed_tutorials.add(tutorial_name)
        
        # Update skill level based on progress
        if len(self.completed_tutorials) >= 3:
            self.user_progress["skill_level"] = "intermediate"
        elif len(self.completed_tutorials) >= 6:
            self.user_progress["skill_level"] = "advanced"
    
    def get_recommended_next_tutorial(self) -> Optional[str]:
        """Get the next recommended tutorial based on progress."""
        # Simple recommendation logic
        if "first_visit" not in self.completed_tutorials:
            return "first_visit"
        elif "four_bar_basics" not in self.completed_tutorials:
            return "four_bar_basics"
        elif "cam_mechanism" not in self.completed_tutorials and self.can_access_tutorial("cam_mechanism"):
            return "cam_mechanism"
        
        return None
    
    def get_progress_summary(self) -> Dict[str, Any]:
        """Get summary of user's learning progress."""
        return {
            "tutorials_completed": len(self.completed_tutorials),
            "skill_level": self.user_progress["skill_level"],
            "mechanisms_explored": len(self.user_progress["mechanisms_viewed"]),
            "next_recommended": self.get_recommended_next_tutorial()
        }