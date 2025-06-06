import os

os.environ["PYOPENGL_PLATFORM"] = "glut"

from .image_to_annotations import image_to_annotations, AnnotationResults
from .annotations_to_animation import annotations_to_animation
from pathlib import Path
import logging
import sys
import shutil
from pkg_resources import resource_filename


def image_to_animation(
    img_fn: str, final_output_dir: str, motion_cfg_fn: str, retarget_cfg_fn: str
):
    """
    Given the image located at img_fn, create annotation files needed for animation in a temporary directory.
    Then create animation from those annotations and motion cfg and retarget cfg.
    The final animation products are copied to final_output_dir.
    """
    logger = logging.getLogger(__name__)
    logger.info(
        f"Starting image_to_animation for {img_fn}. Final output intended for {final_output_dir}"
    )

    # Step 1: Create annotations in a temporary directory managed by image_to_annotations
    annotation_results = image_to_annotations(img_fn)

    if not annotation_results:
        logger.error(
            f"Failed to generate annotations for {img_fn}. Aborting animation pipeline."
        )
        return

    temp_char_anno_dir = annotation_results["output_dir"]
    logger.info(
        f"Annotations generated successfully in temporary directory: {temp_char_anno_dir}"
    )

    # Step 2: Create the animation using the annotations from the temporary directory
    # annotations_to_animation will produce output (video/frames) inside temp_char_anno_dir
    try:
        annotations_to_animation(temp_char_anno_dir, motion_cfg_fn, retarget_cfg_fn)
        logger.info(
            f"Animation processing complete for annotations in {temp_char_anno_dir}"
        )
    except Exception as e:
        logger.error(f"Error during annotations_to_animation: {e}", exc_info=True)
        # Decide if we should still try to copy partial results or just abort
        return  # Abort if animation rendering fails

    # Step 3: Copy results from the temporary annotation directory to the final_output_dir
    # This assumes final_output_dir is a directory where the user expects to find the animation video/frames.
    # We need to decide what to copy. Typically, it might be video.gif or a frames/ subfolder.

    Path(final_output_dir).mkdir(parents=True, exist_ok=True)
    logger.info(
        f"Copying animation results from {temp_char_anno_dir} to {final_output_dir}"
    )

    # Example: Copy common outputs. Adjust based on what annotations_to_animation produces.
    files_to_copy = ["video.gif", "video.mp4"]  # Common video outputs
    dirs_to_copy = ["frames"]  # If image sequences are generated

    copied_something = False
    for filename in files_to_copy:
        src_file = Path(temp_char_anno_dir) / filename
        dst_file = Path(final_output_dir) / filename
        if src_file.exists():
            try:
                shutil.copy2(src_file, dst_file)
                logger.info(f"Copied {src_file} to {dst_file}")
                copied_something = True
            except Exception as e:
                logger.error(f"Failed to copy {src_file} to {dst_file}: {e}")

    for dirname in dirs_to_copy:
        src_dir = Path(temp_char_anno_dir) / dirname
        dst_dir = Path(final_output_dir) / dirname
        if src_dir.is_dir():
            try:
                if dst_dir.exists():  # shutil.copytree fails if dst exists
                    shutil.rmtree(dst_dir)
                shutil.copytree(src_dir, dst_dir)
                logger.info(f"Copied directory {src_dir} to {dst_dir}")
                copied_something = True
            except Exception as e:
                logger.error(f"Failed to copy directory {src_dir} to {dst_dir}: {e}")

    if copied_something:
        logger.info(f"Animation results successfully copied to {final_output_dir}")
    else:
        logger.warning(
            f"No standard animation output (e.g., video.gif, frames/) found in {temp_char_anno_dir} to copy."
        )

    # Optionally, copy the char_cfg.yaml and other source assets if the user expects the final_output_dir
    # to be a complete representation of the character for animation.
    # For now, focus is on the animation product itself.


if __name__ == "__main__":
    log_dir = Path("./logs")
    log_dir.mkdir(exist_ok=True, parents=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "image_to_animation_main.log"),
            logging.StreamHandler(),
        ],
    )
    logger_main = logging.getLogger(__name__)

    if len(sys.argv) < 3:
        logger_main.error(
            "Usage: python image_to_animation.py <image_path> <final_output_directory> [motion_cfg] [retarget_cfg]"
        )
        sys.exit(1)

    img_fn_arg = sys.argv[1]
    final_output_dir_arg = sys.argv[2]

    motion_cfg_fn_arg = resource_filename(__name__, "config/motion/dab.yaml")
    if len(sys.argv) > 3:
        motion_cfg_fn_arg = sys.argv[3]

    retarget_cfg_fn_arg = resource_filename(__name__, "config/retarget/fair1_ppf.yaml")
    if len(sys.argv) > 4:
        retarget_cfg_fn_arg = sys.argv[4]

    logger_main.info(
        f"Running image_to_animation for image: {img_fn_arg}, output to: {final_output_dir_arg}"
    )
    image_to_animation(
        img_fn_arg, final_output_dir_arg, motion_cfg_fn_arg, retarget_cfg_fn_arg
    )
