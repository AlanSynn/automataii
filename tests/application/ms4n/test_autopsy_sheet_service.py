from ms4n_helpers import make_episode

from automataii.application.ms4n import AutopsySheetService


def test_autopsy_sheet_includes_breakdown_repair_explanation_and_facilitator_move():
    text = AutopsySheetService().render_markdown(make_episode())
    assert "ep_001" in text
    assert "jam" in text
    assert "move_pivot" in text
    assert "Moving the pivot" in text
    assert "predict_observe_explain" in text
