from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Dict

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

try:
    from .ai_advisor import generate_actionable_advice
    from .models import HeatFeedbackRequest, HeatFeedbackResponse, OptimizeRequest, OptimizeResponse
    from .optimizer import (
        apply_heat_feedback,
        load_scrap_config,
        load_steel_grades,
        optimize_scrap_mix,
        save_scrap_config,
    )
except ImportError:
    from ai_advisor import generate_actionable_advice
    from models import HeatFeedbackRequest, HeatFeedbackResponse, OptimizeRequest, OptimizeResponse
    from optimizer import (
        apply_heat_feedback,
        load_scrap_config,
        load_steel_grades,
        optimize_scrap_mix,
        save_scrap_config,
    )


app = FastAPI(title="KSL Scrap Mix Optimization", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/config")
def get_config() -> Dict:
    return {
        "steel_grades": load_steel_grades(),
        "scrap_config": load_scrap_config(),
    }


@app.post("/optimize", response_model=OptimizeResponse)
def optimize(request: OptimizeRequest) -> OptimizeResponse:
    try:
        result = optimize_scrap_mix(
            grade_name=request.grade,
            heat_size_tons=request.heat_size_tons,
            inventory_tons=request.inventory_tons,
            std_dev_overrides=request.std_dev_overrides,
        )
        advisor = generate_actionable_advice(
            request_payload=request.model_dump(),
            optimize_result=result,
            scrap_config=load_scrap_config(),
        )
        result.update(advisor)
        return OptimizeResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Optimization error: {exc}") from exc


@app.post("/upload_inventory")
async def upload_inventory(file: UploadFile = File(...)) -> Dict:
    if not file.filename.lower().endswith((".xlsx", ".xlsm", ".xls")):
        raise HTTPException(status_code=400, detail="Upload Excel file (.xlsx/.xlsm/.xls).")

    raw = await file.read()
    try:
        df = pd.read_excel(BytesIO(raw))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Cannot read Excel: {exc}") from exc

    required_cols = {"scrap_grade", "available_tons"}
    missing = required_cols - set(df.columns)
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing columns: {sorted(missing)}")

    config = load_scrap_config()
    scrap_grades = config["scrap_grades"]

    updated = []
    for _, row in df.iterrows():
        scrap = str(row["scrap_grade"]).strip()
        if scrap not in scrap_grades:
            continue
        scrap_grades[scrap]["available_tons"] = max(0.0, float(row["available_tons"]))

        cu_std = row.get("std_dev_cu")
        sn_std = row.get("std_dev_sn")
        chemistry = scrap_grades[scrap].setdefault("chemistry", {})
        chemistry.setdefault("Cu", {"mean": 0.0, "std_dev": 0.0})
        chemistry.setdefault("Sn", {"mean": 0.0, "std_dev": 0.0})

        if pd.notna(cu_std):
            chemistry["Cu"]["std_dev"] = max(0.0, float(cu_std))
        if pd.notna(sn_std):
            chemistry["Sn"]["std_dev"] = max(0.0, float(sn_std))
        updated.append(scrap)

    save_scrap_config(config)
    return {
        "status": "updated",
        "updated_scrap_grades": sorted(set(updated)),
        "scrap_config": config,
    }


@app.post("/update_heat_feedback", response_model=HeatFeedbackResponse)
def update_heat_feedback(request: HeatFeedbackRequest) -> HeatFeedbackResponse:
    updated = apply_heat_feedback(
        mix_tons=request.mix_tons,
        predicted_chemistry=request.predicted_chemistry,
        actual_tapped_chemistry=request.actual_tapped_chemistry,
        alpha=request.alpha,
    )
    return HeatFeedbackResponse(status="updated", updated_scrap_grades=updated)
