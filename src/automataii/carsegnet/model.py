import logging

import torch
import torch.nn as nn
import torch.nn.functional as F
from segment_anything import sam_model_registry
from segment_anything.modeling import ImageEncoderViT, MaskDecoder, PromptEncoder
from torchvision.ops.boxes import masks_to_boxes

logger = logging.getLogger(__name__)

# Define number of classes for each stage and total
NUM_STAGE1_CLASSES = 4  # 0:bg, 1:head, 2:body, 3:limbs (example)
NUM_STAGE2_CLASSES = 14  # Non-facial parts + background
NUM_STAGE3_CLASSES = 11  # Facial parts + background within face crop
NUM_TOTAL_CLASSES = 25  # Total semantic labels

# Placeholder mapping (Needs actual dataset definition)
# Map Stage 2 indices (0-13) to Final indices (0-24)
STAGE2_TO_FINAL_MAP = {i: i for i in range(NUM_STAGE2_CLASSES)}  # Example: direct map
# Map Stage 3 indices (0-10) within face crop to Final indices (0-24)
STAGE3_TO_FINAL_MAP = {
    i: i + NUM_STAGE2_CLASSES for i in range(1, NUM_STAGE3_CLASSES)
}  # Example: offset map, skipping bg
STAGE3_BACKGROUND_IDX = 0  # Assuming index 0 is background in stage 3
FACE_CLASS_INDEX_STAGE2 = 1  # Placeholder index for 'face' in stage 2 output


class CharSegNet(nn.Module):
    """
    Hierarchical Semantic Segmentation Model for Childlike Drawings (CharSegNet).

    Builds upon the Segment Anything Model (SAM) architecture, adapting it for
    semantic part parsing of figure drawings via a three-stage process.

    Args:
        sam_model_type (str): The type of SAM ViT backbone to use (e.g., 'vit_h').
        sam_checkpoint (str): Path to the pre-trained SAM checkpoint file.
        freeze_encoder (bool): If True, freezes the weights of the SAM image encoder.
                               Defaults to False, allowing fine-tuning.
    """

    def __init__(
        self,
        sam_model_type: str = "vit_h",  # Default to largest model
        sam_checkpoint: str | None = None,
        freeze_encoder: bool = False,
    ) -> None:
        super().__init__()

        if sam_checkpoint is None:
            logger.warning(
                "No SAM checkpoint provided. Initializing SAM components from scratch. "
                "For best results, provide a pre-trained SAM checkpoint."
            )
            self.sam = sam_model_registry[sam_model_type]()
        else:
            logger.info(f"Loading SAM model {sam_model_type} from {sam_checkpoint}")
            self.sam = sam_model_registry[sam_model_type](checkpoint=sam_checkpoint)

        self.image_encoder: ImageEncoderViT = self.sam.image_encoder
        self.original_mask_decoder: MaskDecoder = self.sam.mask_decoder
        self.original_prompt_encoder: PromptEncoder = self.sam.prompt_encoder

        if freeze_encoder:
            logger.info("Freezing SAM image encoder weights.")
            for param in self.image_encoder.parameters():
                param.requires_grad = False

        self.decoder_stage1 = self._create_adapted_decoder(NUM_STAGE1_CLASSES)
        self.prompt_encoder_stage2 = self._create_prompt_encoder()
        self.decoder_stage2 = self._create_adapted_decoder(NUM_STAGE2_CLASSES)
        self.prompt_encoder_stage3 = self._create_prompt_encoder()
        self.decoder_stage3 = self._create_adapted_decoder(NUM_STAGE3_CLASSES)

        logger.info("Randomly initializing weights for stage-specific prompt encoders.")

        # Image format assumed by SAM preprocessor
        self.pixel_mean = torch.Tensor([123.675, 116.28, 103.53]).view(-1, 1, 1)
        self.pixel_std = torch.Tensor([58.395, 57.12, 57.375]).view(-1, 1, 1)
        self.input_size = self.image_encoder.img_size

    def _create_adapted_decoder(self, num_classes: int) -> MaskDecoder:
        """Creates a MaskDecoder adapted for semantic segmentation."""
        # Create a new MaskDecoder instance. We can copy configuration from
        # the original SAM decoder but adjust the output head for num_classes.
        # Note: This requires understanding MaskDecoder internals or potentially
        # modifying it if the output head isn't easily replaceable.
        # For simplicity here, we create a new one with potentially learned params.
        # A more direct approach might involve replacing sam.mask_decoder.output_hypernetworks_mlps
        decoder = MaskDecoder(
            transformer_dim=self.original_mask_decoder.transformer_dim,
            transformer=self.original_mask_decoder.transformer,
            num_multimask_outputs=self.original_mask_decoder.num_multimask_outputs,
            activation=type(self.original_mask_decoder.activation),
            iou_head_depth=self.original_mask_decoder.iou_head_depth,
            iou_head_hidden_dim=self.original_mask_decoder.iou_head_hidden_dim,
        )
        # Replace or add the final layer for semantic class prediction
        # SAM's decoder outputs masks + IoU scores. We need class logits.
        # This might involve adding a new MLP head or modifying existing ones.
        # Placeholder: Add a simple conv layer for class prediction
        # Actual implementation might need to modify decoder's forward method or internal layers.
        decoder.output_semantic_head = nn.Conv2d(
            decoder.transformer_dim, num_classes, kernel_size=1
        )
        return decoder

    def _create_prompt_encoder(self) -> PromptEncoder:
        """
        Creates a new PromptEncoder instance for mask/semantic guidance.

        Based on the paper, these prompt encoders are randomly initialized.
        We replicate the structure of SAM's prompt encoder.
        """
        # Replicate parameters from the original prompt encoder if possible
        # Note: This assumes the structure is suitable for encoding masks directly.
        # The paper mentions repurposing SAM's prompt encoder - details might vary.
        encoder = PromptEncoder(
            embed_dim=self.original_prompt_encoder.embed_dim,
            image_embedding_size=self.original_prompt_encoder.image_embedding_size,
            input_image_size=self.original_prompt_encoder.input_image_size,
            mask_in_chans=self.original_prompt_encoder.mask_in_chans,
            # activation=type(self.original_prompt_encoder.activation) # Causing issues
        )
        # Random initialization happens by default when creating nn.Module layers
        return encoder

    def _preprocess(self, x: torch.Tensor) -> torch.Tensor:
        """Normalize pixel values and pad to a square input."""
        # Normalize colors
        x = (x - self.pixel_mean.to(x.device)) / self.pixel_std.to(x.device)

        # Pad
        h, w = x.shape[-2:]
        padh = self.input_size - h
        padw = self.input_size - w
        x = F.pad(x, (0, padw, 0, padh))
        return x

    def _get_face_crops_and_masks(
        self, image: torch.Tensor, stage2_logits: torch.Tensor, face_class_index: int
    ) -> tuple[
        list[torch.Tensor | None],
        list[torch.Tensor | None],
        list[list[int] | None],
    ]:
        """Get face crops, masks, and bounding boxes based on Stage 2 output.

        Returns:
            Tuple containing lists (one element per batch item):
            - List of cropped face images (or None if no face detected).
            - List of binary face masks within the crop (or None).
            - List of bounding boxes [x1, y1, x2, y2] (or None).
        """
        batch_size = image.shape[0]
        face_crops = [None] * batch_size
        face_masks = [None] * batch_size
        face_bboxes = [None] * batch_size

        # Get probabilities for the face class
        face_probs = torch.softmax(stage2_logits, dim=1)[:, face_class_index, :, :]
        # Thresholding or finding the largest connected component might be needed
        # Simple thresholding for now:
        face_binary_mask_full = face_probs > 0.5  # (B, H, W)

        if not face_binary_mask_full.any():
            logger.warning("No face region found based on Stage 2 output.")
            return face_crops, face_masks, face_bboxes

        # Get bounding boxes for each item in the batch
        # masks_to_boxes expects boolean masks (B, H, W)
        try:
            boxes = masks_to_boxes(face_binary_mask_full)
        except Exception as e:
            logger.error(f"Error getting bounding boxes from masks: {e}")
            # Handle cases where masks might be empty after slicing/processing
            return face_crops, face_masks, face_bboxes

        for i in range(batch_size):
            if not face_binary_mask_full[i].any():
                continue  # No face found in this batch item

            box = boxes[i].round().int()
            x1, y1, x2, y2 = box.tolist()

            # Ensure box coordinates are within image bounds and valid
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(image.shape[3], x2), min(image.shape[2], y2)
            if x1 >= x2 or y1 >= y2:
                logger.warning(
                    f"Invalid bounding box for batch {i}: {[x1, y1, x2, y2]}"
                )
                continue

            # Crop the original image and the binary face mask
            crop = image[i : i + 1, :, y1:y2, x1:x2]
            mask_crop = (
                face_binary_mask_full[i : i + 1, y1:y2, x1:x2].unsqueeze(1).float()
            )  # (1, 1, H_crop, W_crop)

            face_crops[i] = crop
            face_masks[i] = mask_crop
            face_bboxes[i] = [x1, y1, x2, y2]

        return face_crops, face_masks, face_bboxes

    def _upsample_logits(
        self, logits: torch.Tensor, target_size: tuple[int, int]
    ) -> torch.Tensor:
        """Upsamples logits to the target spatial size."""
        # Expects logits shape (B, C, H, W)
        if logits.shape[-2:] == target_size:
            return logits
        return F.interpolate(
            logits,
            size=target_size,
            mode="bilinear",
            align_corners=False,
        )



if __name__ == "__main__":
    # Example Usage (Requires a SAM checkpoint file)
    import os


    # --- Configuration ---
    DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    # Make sure SAM_CHECKPOINT path is correct
    SAM_CHECKPOINT_DIR = os.path.expanduser("~/Downloads/checkpoints")  # Or adjust path
    SAM_CHECKPOINT = os.path.join(SAM_CHECKPOINT_DIR, "sam_vit_h_4b8939.pth")
    SAM_MODEL_TYPE = "vit_h"  # Must match the checkpoint
    # Example image path (replace with your image)
    # IMAGE_PATH = "path/to/your/childlike_drawing.png"

    # --- Logging Setup ---
    logging.basicConfig(level=logging.INFO)

    # --- Check if Checkpoint Exists ---
    if not os.path.isfile(SAM_CHECKPOINT):
        logger.error(f"SAM Checkpoint not found at: {SAM_CHECKPOINT}")
        logger.error(
            "Please download the SAM ViT-H checkpoint (e.g., from https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth) "
        )
        logger.error(
            f"and place it in {SAM_CHECKPOINT_DIR} or update the SAM_CHECKPOINT variable."
        )
        exit()

    # --- Model Initialization ---
    logger.info(f"Initializing CharSegNet ({SAM_MODEL_TYPE}) on {DEVICE}...")
    try:
        model = CharSegNet(sam_model_type=SAM_MODEL_TYPE, sam_checkpoint=SAM_CHECKPOINT)
        model.to(DEVICE)
        model.eval()  # Set to evaluation mode for inference example
        logger.info("Model initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize model: {e}", exc_info=True)
        exit()

    # --- Load and Prepare Image ---
    # logger.info(f"Loading image from: {IMAGE_PATH}")
    # if not os.path.isfile(IMAGE_PATH):
    #     logger.error(f"Image file not found: {IMAGE_PATH}")
    #     exit()
    # image_bgr = cv2.imread(IMAGE_PATH)
    # if image_bgr is None:
    #     logger.error(f"Failed to load image: {IMAGE_PATH}")
    #     exit()
    # image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    # # Convert to tensor (H, W, C) -> (C, H, W)
    # image_tensor = torch.from_numpy(image_rgb).permute(2, 0, 1).unsqueeze(0).float() # (B, C, H, W)
    # logger.info(f"Loaded image with shape: {image_tensor.shape}")

    # --- Use Dummy Input Instead (as image path is commented out) ---
    input_size_h, input_size_w = 512, 600  # Example non-square size
    dummy_image = (
        torch.rand(1, 3, input_size_h, input_size_w) * 255.0
    )  # Simulate image pixel range
    image_tensor = dummy_image.to(DEVICE)
    logger.info(f"Using dummy input tensor: {image_tensor.shape}")

    # --- Forward Pass ---
    logger.info("Performing forward pass...")
    with torch.no_grad():  # Disable gradient calculations for inference
        try:
            output = model(image_tensor)
            logger.info("Forward pass completed.")

            # --- Output Analysis ---
            logger.info("Output dictionary keys: %s", list(output.keys()))
            for key, tensor in output.items():
                if tensor is not None:
                    logger.info(f"  Output '{key}' shape: {tensor.shape}")
                else:
                    logger.info(f"  Output '{key}' is None")

            # Example: Get final predicted class labels
            if output["final_logits"] is not None:
                final_predictions = torch.argmax(output["final_logits"], dim=1)
                logger.info(f"Final prediction labels shape: {final_predictions.shape}")
                # TODO: Visualize the segmentation map (e.g., using matplotlib)
            else:
                logger.warning("Final logits were None.")

        except Exception as e:
            logger.error(f"Forward pass failed: {e}", exc_info=True)

    logger.info("Example usage finished.")

    # TODO LIST:
    # - [ ] Define accurate class indices and mappings (NUM_*, *_TO_FINAL_MAP, FACE_CLASS_INDEX_STAGE2, STAGE3_BACKGROUND_IDX) based on ChildlikeSHAPES dataset.
    # - [ ] Verify SAM preprocessing (_preprocess) matches the fine-tuning process used in the paper.
    # - [ ] Investigate cropping image_embeddings directly vs. re-encoding cropped image in Stage 3 for efficiency.
    # - [ ] Check if positional encoding (PE) needs adjustment for cropped features in Stage 3 decoder call.
    # - [ ] Refine the face detection logic in _get_face_crops_and_masks (e.g., largest component instead of simple threshold).
    # - [ ] Refine the final logit combination logic, especially handling overlaps and background class assignment.
    # - [ ] Implement data loading for ChildlikeSHAPES dataset.
    # - [ ] Define appropriate loss functions (Dice, Focal, CrossEntropy, or combination).
    # - [ ] Implement the training loop.
    # - [ ] Add visualization code for segmentation masks.
    # - [ ] Add comprehensive unit and integration tests (mocking SAM/checkpoints where needed).
