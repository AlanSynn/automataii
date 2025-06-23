# Copyright (c) Meta Platforms, Inc. and affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import logging
import os
import sys
from pathlib import Path

import animated_drawings.render
import yaml
from pkg_resources import resource_filename


def annotations_to_animation(
    char_anno_dir: str,
    motion_cfg_fn: str,
    retarget_cfg_fn: str,
    use_image_sequence=False,
):
    """
    Given a path to a directory with character annotations, a motion configuration file, and a retarget configuration file,
    creates an animation and saves it to {annotation_dir}/video.png

    Args:
        char_anno_dir: Directory containing character annotations
        motion_cfg_fn: Path to motion configuration file
        retarget_cfg_fn: Path to retarget configuration file
        use_image_sequence: If True, render as image sequence instead of video (helps with OpenGL issues)
    """

    # package character_cfg_fn, motion_cfg_fn, and retarget_cfg_fn
    animated_drawing_dict = {
        "character_cfg": str(Path(char_anno_dir, "char_cfg.yaml").resolve()),
        "motion_cfg": str(Path(motion_cfg_fn).resolve()),
        "retarget_cfg": str(Path(retarget_cfg_fn).resolve()),
    }

    # Create frames directory if using image sequence
    if use_image_sequence:
        frames_dir = Path(char_anno_dir, "frames")
        frames_dir.mkdir(exist_ok=True, parents=True)
        render_mode = "image_sequence"
        output_path = str(frames_dir.resolve())
    else:
        render_mode = "video_render"
        output_path = str(Path(char_anno_dir, "video.gif").resolve())

    # create mvc config
    mvc_cfg = {
        "scene": {
            "ANIMATED_CHARACTERS": [animated_drawing_dict]
        },  # add the character to the scene
        "controller": {
            "MODE": render_mode,  # 'video_render', 'image_sequence', or 'interactive'
            "OUTPUT_VIDEO_PATH": output_path,
        },  # set the output location
    }

    # write the new mvc config file out
    output_mvc_cfn_fn = str(Path(char_anno_dir, "mvc_cfg.yaml"))
    with open(output_mvc_cfn_fn, "w") as f:
        yaml.dump(dict(mvc_cfg), f)

    try:
        # Try to render with the current configuration
        animated_drawings.render.start(output_mvc_cfn_fn)
    except Exception as e:
        logging.warning(f"Initial rendering attempt failed: {e}")

        if not use_image_sequence:
            logging.info("Falling back to image sequence rendering mode")
            # Try again with image sequence mode
            annotations_to_animation(
                char_anno_dir, motion_cfg_fn, retarget_cfg_fn, use_image_sequence=True
            )


if __name__ == "__main__":
    from ..utils.paths import get_project_root
    project_root = get_project_root()
    log_dir = project_root / "logs"
    log_dir.mkdir(exist_ok=True, parents=True)
    logging.basicConfig(filename=f"{log_dir}/log.txt", level=logging.DEBUG)

    char_anno_dir = sys.argv[1]
    if len(sys.argv) > 2:
        motion_cfg_fn = sys.argv[2]
    else:
        motion_cfg_fn = resource_filename(__name__, "config/motion/dab.yaml")
    if len(sys.argv) > 3:
        retarget_cfg_fn = sys.argv[3]
    else:
        retarget_cfg_fn = resource_filename(__name__, "config/retarget/fair1_ppf.yaml")

    # Check if we should use image sequence mode (helps with OpenGL issues)
    use_image_sequence = os.environ.get("USE_IMAGE_SEQUENCE", "0").lower() in (
        "1",
        "true",
        "yes",
    )

    annotations_to_animation(
        char_anno_dir, motion_cfg_fn, retarget_cfg_fn, use_image_sequence
    )
