import pytest
import torch
import os

# Adjust import path based on your project structure
# Assuming 'tests' is at the root level alongside 'src'
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.automataii.carsegnet.model import CharSegNet, NUM_TOTAL_CLASSES

# Path to a dummy or actual SAM checkpoint for testing
# You might need to download a smaller one or mock the loading process
# For now, assume it exists or the test will skip/fail gracefully.
SAM_CHECKPOINT_PATH = "sam_vit_h_4b8939.pth" # Or use a smaller model like vit_b
SAM_MODEL_TYPE = "vit_h"

# Check if the checkpoint exists, otherwise skip tests requiring it
checkpoint_exists = os.path.isfile(SAM_CHECKPOINT_PATH)
requires_checkpoint = pytest.mark.skipif(not checkpoint_exists, reason=f"SAM checkpoint {SAM_CHECKPOINT_PATH} not found")

@requires_checkpoint
def test_model_instantiation():
    """Tests if the CharSegNet model can be instantiated."""
    try:
        model = CharSegNet(sam_model_type=SAM_MODEL_TYPE, sam_checkpoint=SAM_CHECKPOINT_PATH)
        assert model is not None
        # Check if submodules exist (even if they are placeholders like nn.Identity)
        assert hasattr(model, 'image_encoder')
        # assert hasattr(model, 'decoder_stage1') # Add assertions once implemented
        # assert hasattr(model, 'decoder_stage2')
        # assert hasattr(model, 'decoder_stage3')
    except Exception as e:
        pytest.fail(f"Model instantiation failed: {e}")

@requires_checkpoint
def test_model_forward_pass():
    """Tests the forward pass with a dummy input."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = CharSegNet(sam_model_type=SAM_MODEL_TYPE, sam_checkpoint=SAM_CHECKPOINT_PATH).to(device).eval()

    # Dummy input (Batch size 1, 3 channels, 1024x1024 for SAM encoder)
    batch_size = 1
    input_tensor = torch.rand(batch_size, 3, 1024, 1024).to(device)

    with torch.no_grad():
        try:
            output = model(input_tensor)
            assert isinstance(output, dict)
            # Check presence and basic shape of output tensors (using placeholder shapes for now)
            assert 'stage1_logits' in output
            assert output['stage1_logits'].shape[0] == batch_size
            assert output['stage1_logits'].shape[1] == 4 # NUM_STAGE1_CLASSES

            assert 'stage2_logits' in output
            assert output['stage2_logits'].shape[0] == batch_size
            assert output['stage2_logits'].shape[1] == 14 # NUM_STAGE2_CLASSES

            assert 'stage3_logits' in output
            assert output['stage3_logits'].shape[0] == batch_size
            assert output['stage3_logits'].shape[1] == 11 # NUM_STAGE3_CLASSES

            assert 'final_logits' in output
            assert output['final_logits'].shape[0] == batch_size
            assert output['final_logits'].shape[1] == NUM_TOTAL_CLASSES
            # Check if final logits spatial dimensions match input (or expected output size)
            assert output['final_logits'].shape[2:] == (1024, 1024) # Assuming direct output at input res for placeholder


        except Exception as e:
            pytest.fail(f"Model forward pass failed: {e}")

# TODO: Add more tests once components are implemented:
# - Test different configurations (e.g., freezing encoder)
# - Test output shapes after implementing actual decoders and upsampling
# - Test individual stage outputs if possible
# - Test on CPU and GPU if feasible
# - Mock SAM loading if checkpoint isn't available in CI environment