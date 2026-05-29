import pytest

from automataii.domain.ms4n.repair_taxonomy import (
    validate_facilitator_move,
    validate_repair_action,
    validate_status,
    validate_suspected_cause,
    validate_symptom,
)


def test_repair_taxonomy_accepts_known_p0_codes():
    assert validate_symptom("jam") == "jam"
    assert validate_suspected_cause("pivot_spacing") == "pivot_spacing"
    assert validate_repair_action("move_pivot") == "move_pivot"
    assert validate_facilitator_move("predict_observe_explain") == "predict_observe_explain"
    assert validate_status("abandoned") == "abandoned"


@pytest.mark.parametrize("code", ["JAM", " jam", "invented_code"])
def test_repair_taxonomy_rejects_unknown_codes(code):
    with pytest.raises(ValueError):
        validate_symptom(code)
