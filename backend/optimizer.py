from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Dict, List, Tuple

import pulp


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SCRAP_CONFIG_PATH = DATA_DIR / "scrap_config.json"
STEEL_GRADES_PATH = DATA_DIR / "steel_grades.json"

RECOVERY = {
    "C": 0.85,
    "Mn": 0.90,
    "Si": 0.30,
    "Cr": 0.70,
    "Mo": 0.85,
    "Ni": 0.90,
    "Cu": 1.00,
    "Sn": 1.00,
    "P": 0.95,
    "S": 0.90,
}

TRAMP_ELEMENTS = {"Cu", "Sn"}


def load_scrap_config() -> Dict:
    with SCRAP_CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_scrap_config(config: Dict) -> None:
    with SCRAP_CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, sort_keys=True)


def load_steel_grades() -> Dict:
    with STEEL_GRADES_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _effective_chem_value(
    chem_data: Dict[str, float],
    element: str,
    yield_factor: float,
    use_safety_margin: bool,
) -> float:
    mean = float(chem_data.get("mean", 0.0))
    std_dev = float(chem_data.get("std_dev", 0.0))
    base = mean + (2.0 * std_dev if use_safety_margin and element in TRAMP_ELEMENTS else 0.0)
    recovery = float(RECOVERY.get(element, 1.0))
    return base * recovery * yield_factor


def _build_element_coeffs(
    scrap_grades: Dict,
    elements: List[str],
    use_safety_margin: bool,
) -> Dict[str, Dict[str, float]]:
    coeffs: Dict[str, Dict[str, float]] = {}
    for scrap_name, scrap in scrap_grades.items():
        yield_factor = float(scrap.get("yield_factor", 1.0))
        chemistry = scrap.get("chemistry", {})
        coeffs[scrap_name] = {}
        for element in elements:
            coeffs[scrap_name][element] = _effective_chem_value(
                chemistry.get(element, {"mean": 0.0, "std_dev": 0.0}),
                element=element,
                yield_factor=yield_factor,
                use_safety_margin=use_safety_margin,
            )
    return coeffs


def _apply_overrides(
    scrap_config: Dict,
    inventory_tons: Dict[str, float] | None,
    std_dev_overrides: Dict[str, Dict[str, float]] | None,
) -> Dict:
    updated = deepcopy(scrap_config)
    scrap_grades = updated["scrap_grades"]

    if inventory_tons:
        for scrap_name, tons in inventory_tons.items():
            if scrap_name in scrap_grades:
                scrap_grades[scrap_name]["available_tons"] = float(tons)

    if std_dev_overrides:
        for scrap_name, element_map in std_dev_overrides.items():
            if scrap_name not in scrap_grades:
                continue
            for element, std_val in element_map.items():
                chemistry = scrap_grades[scrap_name].setdefault("chemistry", {})
                chem_item = chemistry.setdefault(element, {"mean": 0.0, "std_dev": 0.0})
                chem_item["std_dev"] = max(0.0, float(std_val))

    return updated


def _solve_core_lp(
    grade_limits: Dict,
    scrap_grades: Dict,
    heat_size_tons: float,
) -> Tuple[pulp.LpStatus, Dict[str, float], float, Dict[str, float], Dict[str, float]]:
    elements = sorted(grade_limits.keys())
    scrap_names = list(scrap_grades.keys())

    coeffs_safe = _build_element_coeffs(scrap_grades, elements, use_safety_margin=True)
    coeffs_mean = _build_element_coeffs(scrap_grades, elements, use_safety_margin=False)

    problem = pulp.LpProblem("ScrapMixOptimization", pulp.LpMinimize)
    x = {
        s: pulp.LpVariable(
            f"x_{s.replace('-', '_').replace(' ', '_')}",
            lowBound=0.0,
            upBound=float(scrap_grades[s]["available_tons"]),
            cat="Continuous",
        )
        for s in scrap_names
    }

    # Objective: Minimize total charge cost.
    problem += pulp.lpSum(float(scrap_grades[s]["cost_inr_per_ton"]) * x[s] for s in scrap_names)

    # Mandatory mass balance from requirement.
    problem += pulp.lpSum(x[s] for s in scrap_names) == heat_size_tons, "MassBalance"

    for element, bounds in grade_limits.items():
        lhs = pulp.lpSum(x[s] * coeffs_safe[s][element] for s in scrap_names)
        if "min" in bounds:
            problem += lhs >= heat_size_tons * float(bounds["min"]), f"{element}_min"
        if "max" in bounds:
            problem += lhs <= heat_size_tons * float(bounds["max"]), f"{element}_max"

    solver = pulp.PULP_CBC_CMD(msg=False)
    problem.solve(solver)

    status = pulp.LpStatus[problem.status]
    if status == "Optimal":
        mix = {s: max(0.0, float(x[s].value() or 0.0)) for s in scrap_names}
        total_cost = sum(float(scrap_grades[s]["cost_inr_per_ton"]) * mix[s] for s in scrap_names)
    else:
        mix = {s: 0.0 for s in scrap_names}
        total_cost = 0.0

    predicted_mean = {}
    predicted_safe = {}
    for element in elements:
        total_mean = sum(mix[s] * coeffs_mean[s][element] for s in scrap_names)
        total_safe = sum(mix[s] * coeffs_safe[s][element] for s in scrap_names)
        predicted_mean[element] = total_mean / heat_size_tons
        predicted_safe[element] = total_safe / heat_size_tons

    return status, mix, total_cost, predicted_mean, predicted_safe


def _diagnose_infeasibility(
    grade_limits: Dict,
    scrap_grades: Dict,
    heat_size_tons: float,
) -> List[str]:
    elements = sorted(grade_limits.keys())
    scrap_names = list(scrap_grades.keys())
    coeffs = _build_element_coeffs(scrap_grades, elements, use_safety_margin=True)

    problem = pulp.LpProblem("InfeasibilityDiagnosis", pulp.LpMinimize)
    x = {
        s: pulp.LpVariable(
            f"x_{s.replace('-', '_').replace(' ', '_')}",
            lowBound=0.0,
            upBound=float(scrap_grades[s]["available_tons"]),
            cat="Continuous",
        )
        for s in scrap_names
    }

    slacks_low = {}
    slacks_high = {}
    for element, bounds in grade_limits.items():
        if "min" in bounds:
            slacks_low[element] = pulp.LpVariable(f"s_low_{element}", lowBound=0.0, cat="Continuous")
        if "max" in bounds:
            slacks_high[element] = pulp.LpVariable(f"s_high_{element}", lowBound=0.0, cat="Continuous")

    problem += (
        1_000_000 * pulp.lpSum(slacks_low.values())
        + 1_000_000 * pulp.lpSum(slacks_high.values())
        + pulp.lpSum(float(scrap_grades[s]["cost_inr_per_ton"]) * x[s] for s in scrap_names)
    )

    problem += pulp.lpSum(x[s] for s in scrap_names) == heat_size_tons, "MassBalance"

    for element, bounds in grade_limits.items():
        lhs = pulp.lpSum(x[s] * coeffs[s][element] for s in scrap_names)
        if "min" in bounds:
            problem += (
                lhs + slacks_low[element] >= heat_size_tons * float(bounds["min"]),
                f"{element}_min",
            )
        if "max" in bounds:
            problem += (
                lhs - slacks_high[element] <= heat_size_tons * float(bounds["max"]),
                f"{element}_max",
            )

    solver = pulp.PULP_CBC_CMD(msg=False)
    problem.solve(solver)

    violations: List[str] = []
    for element, slack in slacks_low.items():
        value = float(slack.value() or 0.0)
        if value > 1e-6:
            violations.append(f"{element} below minimum by {value / heat_size_tons:.4f} wt%")
    for element, slack in slacks_high.items():
        value = float(slack.value() or 0.0)
        if value > 1e-6:
            violations.append(f"{element} above maximum by {value / heat_size_tons:.4f} wt%")

    return violations


def _suggest_actions(violations: List[str], scrap_grades: Dict, heat_size_tons: float) -> List[str]:
    suggestions: List[str] = []
    joined = " | ".join(violations)

    if "Cu above maximum" in joined or "Sn above maximum" in joined:
        suggestions.append("Increase DRI share to dilute Cu/Sn.")
        suggestions.append("Reduce Auto Scrap and high-tramp scrap usage.")

    if "C below minimum" in joined:
        suggestions.append("Add Pig Iron to raise carbon.")
    elif "C above maximum" in joined:
        suggestions.append("Increase low-carbon scrap/DRI and reduce Pig Iron or high-carbon scrap.")

    if any(token in joined for token in ["Cr below minimum", "Mo below minimum", "Ni below minimum"]):
        suggestions.append("Current scrap set is alloy-deficient for Cr/Mo/Ni; charge alloy-rich scrap or alloy additions.")

    available_total = sum(float(item.get("available_tons", 0.0)) for item in scrap_grades.values())
    if available_total < heat_size_tons:
        suggestions.append("Adjust heat size to match available inventory.")

    if not suggestions:
        suggestions = [
            "Increase DRI share.",
            "Reduce Auto Scrap.",
            "Add Pig Iron.",
            "Adjust heat size.",
        ]

    # Preserve order and uniqueness.
    deduped = []
    for item in suggestions:
        if item not in deduped:
            deduped.append(item)
    return deduped


def optimize_scrap_mix(
    grade_name: str,
    heat_size_tons: float,
    inventory_tons: Dict[str, float] | None = None,
    std_dev_overrides: Dict[str, Dict[str, float]] | None = None,
) -> Dict:
    steel_grades = load_steel_grades()
    if grade_name not in steel_grades:
        raise ValueError(f"Unknown grade: {grade_name}")

    base_scrap_config = load_scrap_config()
    effective_config = _apply_overrides(base_scrap_config, inventory_tons, std_dev_overrides)

    scrap_grades = effective_config["scrap_grades"]
    grade_limits = steel_grades[grade_name]

    status, mix, total_cost, predicted_mean, predicted_safe = _solve_core_lp(
        grade_limits=grade_limits,
        scrap_grades=scrap_grades,
        heat_size_tons=heat_size_tons,
    )

    feasible = status == "Optimal"
    violations: List[str] = []
    suggestions: List[str] = []
    if not feasible:
        violations = _diagnose_infeasibility(
            grade_limits=grade_limits,
            scrap_grades=scrap_grades,
            heat_size_tons=heat_size_tons,
        )
        suggestions = _suggest_actions(violations, scrap_grades, heat_size_tons)

    tramp_warnings: List[str] = []
    for tramp in sorted(TRAMP_ELEMENTS):
        max_limit = grade_limits.get(tramp, {}).get("max")
        if max_limit is None:
            continue
        safe_val = predicted_safe.get(tramp, 0.0)
        if safe_val > 0.95 * float(max_limit):
            tramp_warnings.append(
                f"{tramp} safety value {safe_val:.4f} wt% is close to max {float(max_limit):.4f} wt%."
            )

    return {
        "feasible": feasible,
        "status": status,
        "mix_tons": mix,
        "predicted_chemistry": predicted_mean,
        "safe_chemistry": predicted_safe,
        "total_cost_inr": total_cost,
        "violations": violations,
        "suggestions": suggestions,
        "tramp_warnings": tramp_warnings,
    }


def apply_heat_feedback(
    mix_tons: Dict[str, float],
    predicted_chemistry: Dict[str, float],
    actual_tapped_chemistry: Dict[str, float],
    alpha: float = 0.1,
) -> List[str]:
    config = load_scrap_config()
    scrap_grades = config["scrap_grades"]
    total_mix = sum(max(0.0, float(v)) for v in mix_tons.values())
    if total_mix <= 0:
        return []

    updated_scrap_names: List[str] = []
    for scrap_name, tons in mix_tons.items():
        if scrap_name not in scrap_grades:
            continue
        frac = max(0.0, float(tons)) / total_mix
        if frac <= 0:
            continue

        chemistry = scrap_grades[scrap_name].setdefault("chemistry", {})
        for element, actual_val in actual_tapped_chemistry.items():
            pred_val = float(predicted_chemistry.get(element, 0.0))
            delta = float(actual_val) - pred_val
            chem_item = chemistry.setdefault(element, {"mean": 0.0, "std_dev": 0.0})
            old_mean = float(chem_item.get("mean", 0.0))
            new_mean = max(0.0, old_mean + float(alpha) * delta * frac)
            chem_item["mean"] = new_mean

        updated_scrap_names.append(scrap_name)

    save_scrap_config(config)
    return sorted(set(updated_scrap_names))
