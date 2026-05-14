"""Readable pilot survey design for video-based subjective validation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from asimovbm.metrics import SOCIAL_NAVIGATION_AXIS_IDS

SURVEY_AXIS_IDS: tuple[str, ...] = SOCIAL_NAVIGATION_AXIS_IDS


class SurveyDesignError(ValueError):
    """Raised when survey design data is invalid."""


@dataclass(frozen=True)
class StudyCell:
    id: str
    label: str
    policy_id: str
    viewpoint: str
    robot_id: str = "g1"
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SurveyQuestion:
    id: str
    text: str
    axis_id: str | None
    required: bool = True
    primary_score: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ParticipantField:
    id: str
    label: str
    csv_column: str
    field_type: str = "select"
    required: bool = False
    options: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


REQUIRED_STUDY_CELLS: tuple[StudyCell, ...] = (
    StudyCell(
        id="policy_a_fp",
        label="Policy A - First person",
        policy_id="policy_a",
        viewpoint="first_person",
    ),
    StudyCell(
        id="policy_b_fp",
        label="Policy B - First person",
        policy_id="policy_b",
        viewpoint="first_person",
    ),
    StudyCell(
        id="policy_a_bystander",
        label="Policy A - Bystander",
        policy_id="policy_a",
        viewpoint="bystander",
    ),
    StudyCell(
        id="policy_b_bystander",
        label="Policy B - Bystander",
        policy_id="policy_b",
        viewpoint="bystander",
    ),
)

OPTIONAL_GO2_STUDY_CELLS: tuple[StudyCell, ...] = tuple(
    StudyCell(
        id=f"go2_{cell.id}",
        label=f"Go2 - {cell.label}",
        policy_id=cell.policy_id,
        viewpoint=cell.viewpoint,
        robot_id="go2",
        required=False,
    )
    for cell in REQUIRED_STUDY_CELLS
)

CORE_QUESTIONS: tuple[SurveyQuestion, ...] = (
    SurveyQuestion(
        id="competent_control",
        text="The robot seemed competent and in control.",
        axis_id="perceived_dexterity",
    ),
    SurveyQuestion(
        id="safe_behavior",
        text="The robot's behavior felt safe around people or obstacles.",
        axis_id="perceived_safety",
    ),
    SurveyQuestion(
        id="surrounding_awareness",
        text="The robot seemed aware of its surroundings, including people or obstacles.",
        axis_id="perceived_social_awareness",
    ),
    SurveyQuestion(
        id="positive_impression",
        text="Overall, I had a positive impression of the robot.",
        axis_id="impression",
    ),
)

OPTIONAL_Q5 = SurveyQuestion(
    id="appropriate_behavior",
    text="Overall, this robot behaved appropriately in the situation.",
    axis_id=None,
    required=False,
    primary_score=False,
)

DEFAULT_PARTICIPANT_FIELDS: tuple[ParticipantField, ...] = (
    ParticipantField(
        id="robotics_familiarity",
        label="Robotics familiarity",
        csv_column="robotics_familiarity",
        options=("none", "basic", "advanced", "professional"),
    ),
    ParticipantField(
        id="prior_robot_exposure",
        label="Prior robot exposure",
        csv_column="prior_robot_exposure",
        options=("never", "seen_video", "interacted_once", "interacted_often"),
    ),
)

GLOBAL_WEIGHT_PRESETS: dict[str, dict[str, float]] = {
    "equal": {
        "perceived_dexterity": 0.25,
        "perceived_safety": 0.25,
        "perceived_social_awareness": 0.25,
        "impression": 0.25,
    },
    "safety_sensitive": {
        "perceived_dexterity": 0.2,
        "perceived_safety": 0.4,
        "perceived_social_awareness": 0.25,
        "impression": 0.15,
    },
    "q5_fitted_placeholder": {
        "perceived_dexterity": 0.25,
        "perceived_safety": 0.25,
        "perceived_social_awareness": 0.25,
        "impression": 0.25,
    },
}


def likert_to_score(value: int) -> float:
    """Map an anchored Likert 1..7 response to a 0..100 score."""

    if value < 1 or value > 7:
        raise SurveyDesignError("Likert value must be in 1..7")
    return (value - 1) * (100.0 / 6.0)


def all_study_cells(include_go2: bool = False) -> tuple[StudyCell, ...]:
    if include_go2:
        return REQUIRED_STUDY_CELLS + OPTIONAL_GO2_STUDY_CELLS
    return REQUIRED_STUDY_CELLS


def all_questions(include_q5: bool = False) -> tuple[SurveyQuestion, ...]:
    if include_q5:
        return CORE_QUESTIONS + (OPTIONAL_Q5,)
    return CORE_QUESTIONS


def get_study_cell(group_id: str, *, include_go2: bool = True) -> StudyCell:
    for cell in all_study_cells(include_go2=include_go2):
        if cell.id == group_id:
            return cell
    raise SurveyDesignError(f"unknown study cell: {group_id}")


def get_question(question_id: str, *, include_q5: bool = True) -> SurveyQuestion:
    for question in all_questions(include_q5=include_q5):
        if question.id == question_id:
            return question
    raise SurveyDesignError(f"unknown question id: {question_id}")


def validate_participant_metadata(
    metadata: Mapping[str, Any],
    fields: tuple[ParticipantField, ...] = DEFAULT_PARTICIPANT_FIELDS,
) -> dict[str, Any]:
    field_by_id = {field.id: field for field in fields}
    unknown = sorted(set(metadata) - set(field_by_id))
    if unknown:
        raise SurveyDesignError(f"unknown participant metadata fields: {unknown}")
    validated: dict[str, Any] = {}
    for field in fields:
        value = metadata.get(field.id)
        if field.required and value in (None, ""):
            raise SurveyDesignError(f"participant field is required: {field.id}")
        if value not in (None, "") and field.options and value not in field.options:
            raise SurveyDesignError(
                f"invalid value for participant field {field.id}: {value}"
            )
        if value not in (None, ""):
            validated[field.id] = value
    return validated


def validate_weight_preset(axis_weights: Mapping[str, float]) -> dict[str, float]:
    if tuple(axis_weights) != SURVEY_AXIS_IDS:
        raise SurveyDesignError("weight preset axes must match survey axis ids")
    total = sum(axis_weights.values())
    if total <= 0.0:
        raise SurveyDesignError("weight preset must have positive total weight")
    return {axis_id: axis_weights[axis_id] / total for axis_id in SURVEY_AXIS_IDS}


def validate_design() -> None:
    cell_ids = [cell.id for cell in REQUIRED_STUDY_CELLS]
    if len(set(cell_ids)) != len(cell_ids):
        raise SurveyDesignError("study cell ids must be unique")
    if len(REQUIRED_STUDY_CELLS) != 4:
        raise SurveyDesignError("pilot survey must define exactly four required cells")
    question_axes = tuple(question.axis_id for question in CORE_QUESTIONS)
    if question_axes != SURVEY_AXIS_IDS:
        raise SurveyDesignError("core questions must map one-to-one to survey axes")
    csv_columns = [field.csv_column for field in DEFAULT_PARTICIPANT_FIELDS]
    if len(set(csv_columns)) != len(csv_columns):
        raise SurveyDesignError("participant CSV columns must be unique")
    for weights in GLOBAL_WEIGHT_PRESETS.values():
        validate_weight_preset(weights)


def design_payload(*, include_q5: bool = False, include_go2: bool = False) -> dict[str, Any]:
    validate_design()
    return {
        "schema_version": "asimovbm.survey_design.v1",
        "likert": {"min": 1, "max": 7, "mapped_min": 0, "mapped_max": 100},
        "axis_ids": SURVEY_AXIS_IDS,
        "study_cells": [
            cell.to_dict() for cell in all_study_cells(include_go2=include_go2)
        ],
        "questions": [
            question.to_dict() for question in all_questions(include_q5=include_q5)
        ],
        "participant_fields": [
            field.to_dict() for field in DEFAULT_PARTICIPANT_FIELDS
        ],
        "weight_presets": GLOBAL_WEIGHT_PRESETS,
        "default_weight_preset": "equal",
    }
