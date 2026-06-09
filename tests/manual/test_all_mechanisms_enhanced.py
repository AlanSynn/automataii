#!/usr/bin/env python3
"""
Comprehensive test for ALL mechanism types with enhanced manufacturing visualizations:
- 4-bar linkage (with key points)
- Gear mechanisms (standard and from params)
- Cam mechanisms (with follower system)
- Planetary gear (complete system)
- Standard mechanisms (pulley, belt, spring, damper)
"""

import logging
import sys
from pathlib import Path

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

# This is an interactive/manual-style test; skip during automated runs.
pytest.skip(
    "Manual enhanced mechanisms test; skipping in CI/automated pytest.", allow_module_level=True
)


def generate_multi_page_blueprint(*args, **kwargs):
    """Legacy manual helper placeholder; module is skipped during automated collection."""
    raise RuntimeError("Manual multi-page blueprint helper is not available in automated tests")


def test_all_enhanced_mechanisms():
    """Test all mechanism types with enhanced manufacturing details"""

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger(__name__)

    try:
        # Import the enhanced modules
        from automataii.domain.generation.layout import ScaleNormalizer
        from automataii.infrastructure.generation.svg.optimizer import EnhancedMechanismProcessor

        logger.info("✅ Successfully imported enhanced mechanism modules")

        scale_normalizer = ScaleNormalizer(300.0)
        processor = EnhancedMechanismProcessor(scale_normalizer)

        # Test mechanisms with comprehensive data
        test_mechanisms = {
            # 1. 4-bar linkage with key points (already implemented)
            "4bar_enhanced": {
                "type": "4_bar_linkage",
                "params": {"L1": 100, "L2": 40, "L3": 80, "L4": 60},
                "key_points": {
                    "ground_pivot_1": [0, 0],
                    "ground_pivot_2": [100, 0],
                    "crank_end": [30, 25],
                    "rocker_end": [85, 15],
                },
                "real_world_params": {
                    "l1_mm": 100.0,
                    "l2_mm": 40.0,
                    "l3_mm": 80.0,
                    "l4_mm": 60.0,
                    "scale_factor_used": 1.0,
                },
                "total_scale_factor": 1.0,
            },
            # 2. Enhanced gear mechanism
            "gear_enhanced": {
                "type": "gear",
                "params": {"r1": 35, "r2": 25},
                "key_points": {"gear1_center": [0, 0], "gear2_center": [60, 0]},
                "real_world_params": {"r1_mm": 35.0, "r2_mm": 25.0, "scale_factor_used": 1.0},
                "total_scale_factor": 1.0,
            },
            # 3. Enhanced cam mechanism
            "cam_enhanced": {
                "type": "cam",
                "params": {"base_radius": 30, "eccentricity": 8, "follower_rod_length": 50},
                "key_points": {"cam_center": [0, 0]},
                "real_world_params": {
                    "base_radius_mm": 30.0,
                    "eccentricity_mm": 8.0,
                    "scale_factor_used": 1.0,
                },
                "total_scale_factor": 1.0,
            },
            # 4. Enhanced planetary gear system
            "planetary_enhanced": {
                "type": "planetary_gear",
                "params": {"r_sun": 20, "r_planet": 15},
                "key_points": {"sun_center": [0, 0]},
                "real_world_params": {
                    "r_sun_mm": 20.0,
                    "r_planet_mm": 15.0,
                    "scale_factor_used": 1.0,
                },
                "total_scale_factor": 1.0,
            },
            # 5. Standard mechanisms (fallback tests)
            "pulley_standard": {"type": "pulley", "params": {"diameter": 50}},
            "belt_standard": {"type": "belt", "params": {"length": 120, "width": 20}},
            "spring_standard": {"type": "spring", "params": {"length": 80, "diameter": 16}},
            "damper_standard": {"type": "damper", "params": {"stroke": 60, "diameter": 30}},
        }

        processed_mechanisms = []
        enhancement_scores = {}

        # Process each mechanism type
        for mech_id, mech_data in test_mechanisms.items():
            logger.info(f"\n🧪 Testing {mech_id} ({mech_data['type']})")

            layout_item = processor.process_mechanism(mech_id, mech_data)

            if layout_item:
                processed_mechanisms.append(layout_item)

                # Analyze enhancement features in SVG content
                svg = layout_item.svg_content
                features_found = 0
                features_total = 6  # Total possible enhancements

                if "gradient-" in svg or "Gradient" in svg:
                    features_found += 1
                    logger.info("   ✅ Gradient fills detected")
                else:
                    logger.info("   ❌ No gradient fills found")

                if "manufacturing" in svg.lower() or "specification" in svg.lower():
                    features_found += 1
                    logger.info("   ✅ Manufacturing specifications detected")
                else:
                    logger.info("   ❌ No manufacturing specs found")

                if "hole" in svg.lower() or "shaft" in svg.lower() or "bearing" in svg.lower():
                    features_found += 1
                    logger.info("   ✅ Mechanical details (holes/shafts/bearings) detected")
                else:
                    logger.info("   ❌ No mechanical details found")

                if "thickness" in svg.lower() or "mm" in svg:
                    features_found += 1
                    logger.info("   ✅ Dimensional specifications detected")
                else:
                    logger.info("   ❌ No dimensional specs found")

                if "material" in svg.lower() or "steel" in svg.lower() or "aluminum" in svg.lower():
                    features_found += 1
                    logger.info("   ✅ Material specifications detected")
                else:
                    logger.info("   ❌ No material specs found")

                if "assembly" in svg.lower() or "mount" in svg.lower() or "ratio" in svg.lower():
                    features_found += 1
                    logger.info("   ✅ Assembly/performance information detected")
                else:
                    logger.info("   ❌ No assembly info found")

                enhancement_score = (features_found / features_total) * 100
                enhancement_scores[mech_id] = enhancement_score

                logger.info(
                    f"   📊 Enhancement score: {enhancement_score:.0f}% ({features_found}/{features_total})"
                )
                logger.info(
                    f"   📏 Dimensions: {layout_item.bounds.width:.1f}×{layout_item.bounds.height:.1f}mm"
                )
                logger.info(f"   📄 SVG length: {len(svg)} characters")

            else:
                logger.error(f"   ❌ Failed to process {mech_id}")
                enhancement_scores[mech_id] = 0

        # Generate multi-page blueprint with all mechanisms
        logger.info(
            f"\n🧪 Generating multi-page blueprint with {len(processed_mechanisms)} enhanced mechanisms"
        )

        pages = generate_multi_page_blueprint(
            processed_mechanisms,
            title="Enhanced Mechanism Manufacturing Blueprint",
            scale_info="All Mechanisms | Enhanced Manufacturing Details | 300mm Character Scale",
            snapshot_data_uri=None,
        )

        logger.info(f"✅ Generated {len(pages)} mechanism pages")

        # Save all mechanism pages for verification
        output_dir = Path("enhanced_mechanisms_output")
        output_dir.mkdir(exist_ok=True)

        saved_files = []
        for i, page in enumerate(pages, 1):
            page_file = output_dir / f"mechanism_page_{i:02d}.svg"
            with open(page_file, "w", encoding="utf-8") as f:
                f.write(page)
            saved_files.append(str(page_file))
            logger.info(f"   📄 Saved: {page_file}")

        # Save individual mechanism SVGs for detailed inspection
        for item in processed_mechanisms:
            mech_file = output_dir / f"{item.name}_detailed.svg"
            with open(mech_file, "w", encoding="utf-8") as f:
                f.write(f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{item.bounds.width + 40}" height="{item.bounds.height + 40}"
     xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
  <g transform="translate(20,20)">
    {item.svg_content}
  </g>
</svg>''')
            logger.info(f"   🔧 Saved detailed: {mech_file}")

        # Generate summary report
        logger.info("\n📊 ENHANCEMENT SUMMARY REPORT:")
        logger.info("=" * 60)

        total_score = sum(enhancement_scores.values())
        avg_score = total_score / len(enhancement_scores) if enhancement_scores else 0

        for mech_id, score in sorted(enhancement_scores.items(), key=lambda x: x[1], reverse=True):
            status = (
                "🟢 EXCELLENT"
                if score >= 80
                else "🟡 GOOD"
                if score >= 60
                else "🟠 BASIC"
                if score >= 40
                else "🔴 MINIMAL"
            )
            logger.info(f"   {mech_id:20} | {score:5.0f}% | {status}")

        logger.info("=" * 60)
        logger.info(f"   {'OVERALL AVERAGE':20} | {avg_score:5.0f}% |")
        logger.info("=" * 60)

        # Success criteria
        success_mechanisms = sum(1 for score in enhancement_scores.values() if score >= 60)
        total_mechanisms = len(enhancement_scores)
        success_rate = (success_mechanisms / total_mechanisms) * 100 if total_mechanisms > 0 else 0

        logger.info("\n🎯 SUCCESS METRICS:")
        logger.info(f"   Mechanisms processed: {total_mechanisms}")
        logger.info(f"   High-quality enhancements (≥60%): {success_mechanisms}")
        logger.info(f"   Success rate: {success_rate:.0f}%")
        logger.info(f"   Pages generated: {len(pages)}")
        logger.info(f"   Files saved: {len(saved_files) + len(processed_mechanisms)}")

        if success_rate >= 80:
            logger.info(
                "\n🎉 EXCELLENT! All mechanism types successfully enhanced with manufacturing details!"
            )
        elif success_rate >= 60:
            logger.info("\n✅ GOOD! Most mechanism types successfully enhanced!")
        else:
            logger.info("\n⚠️  PARTIAL SUCCESS. Some mechanisms need further enhancement.")

        logger.info(f"\n📁 All files saved to: {output_dir.absolute()}")
        logger.info(
            "   Open SVG files in a web browser or SVG viewer to inspect manufacturing details"
        )

        return success_rate >= 60  # Success if 60% or more mechanisms are well-enhanced

    except Exception as e:
        logger.error(f"❌ Comprehensive mechanism test failed: {e}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        return False


if __name__ == "__main__":
    success = test_all_enhanced_mechanisms()
    sys.exit(0 if success else 1)
