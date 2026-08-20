from __future__ import annotations

import pytest

from asimovbm.survey.survey_design import (
    CORE_QUESTIONS,
    DEFAULT_PARTICIPANT_FIELDS,
    REQUIRED_STUDY_CELLS,
    SurveyDesignError,
    design_payload,
    likert_to_score,
    validate_design,
    validate_participant_metadata,
)


def test_design_defines_four_required_study_cells() -> None:
    validate_design()

    assert {cell.id for cell in REQUIRED_STUDY_CELLS} == {
        "policy_a_fp",
        "policy_b_fp",
        "policy_a_bystander",
        "policy_b_bystander",
    }


def test_core_questions_map_one_to_one_to_axes() -> None:
    assert [question.axis_id for question in CORE_QUESTIONS] == [
        "perceived_dexterity",
        "perceived_safety",
        "perceived_social_awareness",
        "impression",
    ]


def test_likert_maps_to_zero_to_one_hundred_scale() -> None:
    assert likert_to_score(1) == 0
    assert likert_to_score(4) == 50
    assert likert_to_score(7) == 100


def test_invalid_likert_value_is_rejected() -> None:
    with pytest.raises(SurveyDesignError):
        likert_to_score(8)


def test_q5_is_optional_and_not_primary() -> None:
    payload = design_payload(include_q5=True)
    q5 = [question for question in payload["questions"] if question["id"] == "appropriate_behavior"][0]

    assert q5["axis_id"] is None
    assert q5["primary_score"] is False


def test_participant_fields_have_stable_csv_columns() -> None:
    assert {field.csv_column for field in DEFAULT_PARTICIPANT_FIELDS} == {
        "robotics_familiarity",
        "prior_robot_exposure",
    }


def test_unknown_participant_metadata_field_is_rejected() -> None:
    with pytest.raises(SurveyDesignError):
        validate_participant_metadata({"email": "person@example.com"})
