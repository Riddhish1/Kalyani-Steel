from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class OptimizeRequest(BaseModel):
    grade: str = Field(..., description="Steel grade key from steel_grades.json")
    heat_size_tons: float = Field(30.0, gt=0)
    inventory_tons: Optional[Dict[str, float]] = Field(
        default=None, description="Optional overrides by scrap name."
    )
    std_dev_overrides: Optional[Dict[str, Dict[str, float]]] = Field(
        default=None,
        description="Optional overrides: {scrap: {Cu: v, Sn: v}}.",
    )


class OptimizeResponse(BaseModel):
    feasible: bool
    status: str
    mix_tons: Dict[str, float]
    predicted_chemistry: Dict[str, float]
    safe_chemistry: Dict[str, float]
    total_cost_inr: float
    violations: List[str]
    suggestions: List[str]
    tramp_warnings: List[str]
    advisor_summary: str
    advisor_actions: List[str]
    advisor_cost_insights: List[str]


class HeatFeedbackRequest(BaseModel):
    mix_tons: Dict[str, float]
    predicted_chemistry: Dict[str, float]
    actual_tapped_chemistry: Dict[str, float]
    alpha: float = Field(0.1, ge=0.0, le=1.0)


class HeatFeedbackResponse(BaseModel):
    status: str
    updated_scrap_grades: List[str]
