import logging
import math


class MechanismGenerator:
    """Analyzes motion paths and suggests/generates mechanical mechanisms.

    (Currently focuses on path analysis; generation logic is placeholder)
    """

    def __init__(self, automata_designer=None):
        # Storing a reference might be useful for accessing parts/scene later
        self.automata_designer = automata_designer
        logging.info("MechanismGenerator initialized.")

    def analyze_path(self, path):
        """Analyzes a QPainterPath to extract basic geometric characteristics."""
        if not path or path.isEmpty():
            logging.warning("analyze_path called with empty path.")
            return None

        # Check if closed (start element equals end vertex)
        # Note: This is a simple check; doesn't guarantee visual closure for complex paths
        is_closed = False
        if path.elementCount() > 1:
            start_el = path.elementAt(0)
            # Find the last vertex element (could be LineTo or CurveTo)
            last_vertex_el = None
            for i in range(path.elementCount() - 1, -1, -1):
                el = path.elementAt(i)
                if el.isCurveTo() or el.isLineTo():
                    last_vertex_el = el
                    break
            if start_el.isMoveTo() and last_vertex_el:
                # Use a small tolerance for floating point comparison
                if (
                    abs(start_el.x - last_vertex_el.x) < 1e-6
                    and abs(start_el.y - last_vertex_el.y) < 1e-6
                ):
                    is_closed = True

        # Get bounding rectangle for dimensions
        bbox = path.boundingRect()
        width = bbox.width()
        height = bbox.height()
        center_x = bbox.center().x()
        center_y = bbox.center().y()

        # Aspect Ratio
        aspect_ratio = width / height if height > 1e-6 else float("inf")

        # Circularity (very rough estimate)
        # Compares average radius to bounding box based radius
        sample_count = 30  # More samples for better estimate
        points = [path.pointAtPercent(i / sample_count) for i in range(sample_count)]
        if not points:
            return {
                "is_closed": is_closed,
                "width": 0,
                "height": 0,
                "aspect_ratio": 0,
                "center": (0, 0),
                "circularity": 0,
            }

        avg_dist_sq = sum(
            (p.x() - center_x) ** 2 + (p.y() - center_y) ** 2 for p in points
        ) / len(points)
        avg_radius = math.sqrt(avg_dist_sq)
        bbox_radius = (width + height) / 4  # Average of half width and half height
        circularity = 0.0
        if bbox_radius > 1e-6:
            # Closer to 1 means more circular
            circularity = 1.0 - abs(avg_radius - bbox_radius) / bbox_radius
            circularity = max(0.0, min(1.0, circularity))  # Clamp to [0, 1]

        analysis = {
            "is_closed": is_closed,
            "width": width,
            "height": height,
            "aspect_ratio": aspect_ratio,
            "center": (center_x, center_y),
            "circularity": circularity,
            "average_radius": avg_radius,
        }
        logging.debug(f"Path analysis results: {analysis}")
        return analysis

    def suggest_mechanism_type(self, path_analysis):
        """Suggests a mechanism type based on path analysis results."""
        if not path_analysis:
            return "Unknown"

        # Simple rules (examples, needs refinement)
        if path_analysis["circularity"] > 0.8 and path_analysis["is_closed"]:
            return (
                "Crank-Slider (approx circular)"
                if path_analysis["aspect_ratio"] > 1.5
                or path_analysis["aspect_ratio"] < 0.66
                else "Rotary Cam / Crank"
            )
        elif (
            abs(path_analysis["aspect_ratio"] - 1.0) < 0.2
            and path_analysis["is_closed"]
        ):
            return "Rotary Cam / Crank"
        elif path_analysis["aspect_ratio"] > 5.0:
            return "Linear Cam / Slider"
        elif path_analysis["aspect_ratio"] < 0.2:
            return "Linear Cam / Slider (Vertical)"
        elif path_analysis["is_closed"]:
            return "Complex Cam / Linkage"
        else:  # Open path
            return "Linkage / Slider"

    def generate_mechanism(self, part_name):
        """Placeholder for generating mechanism details.

        This would involve selecting a mechanism type, determining parameters
        (link lengths, cam profile, etc.), and potentially adding new
        visual elements to the scene.
        """
        if not self.automata_designer:
            logging.warning(
                "MechanismGenerator needs reference to AutomataDesigner to access parts."
            )
            return None

        part_item = self.automata_designer.editor_items.get(part_name)
        if not part_item:
            logging.error(f"Part '{part_name}' not found in editor items.")
            return None
        if not part_item.motion_path or part_item.motion_path.isEmpty():
            logging.warning(f"Part '{part_name}' has no motion path defined.")
            return None

        analysis = self.analyze_path(part_item.motion_path)
        suggested_type = self.suggest_mechanism_type(analysis)

        logging.info(f"Suggested mechanism for '{part_name}': {suggested_type}")

        # --- Placeholder: Actual Generation Logic Would Go Here --- #
        # Example: If type is Cam, call cam generation
        # if "Cam" in suggested_type:
        #     cam_profile = self.generate_cam_profile(part_item.motion_path, ...)
        #     # Add cam visuals to scene
        # elif "Linkage" in suggested_type:
        #     link_lengths = self.design_linkage(part_item.motion_path, ...)
        #     # Add linkage visuals

        print(
            f"Mechanism generation for '{part_name}' (Type: {suggested_type}) not fully implemented."
        )
        # Return some representation of the generated mechanism (e.g., parameters)
        return {"type": suggested_type, "parameters": "Not Implemented"}
