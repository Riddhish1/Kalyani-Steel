from __future__ import annotations

import json
import os
from typing import Dict, List

try:
    from openai import OpenAI
except Exception:  # noqa: BLE001
    OpenAI = None


def _fallback_actions(result: Dict) -> Dict[str, List[str] | str]:
    mix = result.get("mix_tons", {})
    total_cost = float(result.get("total_cost_inr", 0.0))
    feasible = bool(result.get("feasible"))
    violations = result.get("violations", [])
    suggestions = result.get("suggestions", [])
    tramp_warnings = result.get("tramp_warnings", [])

    charged_items = sorted(
        [(name, float(tons)) for name, tons in mix.items() if float(tons) > 1e-6],
        key=lambda x: x[1],
        reverse=True,
    )
    top_mix = [f"{name}: {tons:.3f} t" for name, tons in charged_items[:4]]

    if feasible:
        summary = (
            f"Feasible mix found. Total heat charge cost is INR {total_cost:,.0f}. "
            f"Top charged inputs: {', '.join(top_mix) if top_mix else 'none'}."
        )
        actions = [
            "Run this mix for current heat after standard safety review.",
            "Track Cu/Sn in tap sample and tighten Auto Scrap if tramp trends upward.",
            "Use heat feedback endpoint after tapping to update scrap chemistry means.",
        ]
    else:
        summary = (
            "No feasible mix with current bounds/inventory. "
            f"Primary violations: {', '.join(violations[:3]) if violations else 'constraint conflict'}."
        )
        actions = suggestions[:]
        if not actions:
            actions = [
                "Increase DRI to dilute tramp and reduce impurity risk.",
                "Reduce Auto Scrap and other high-tramp streams.",
                "Adjust heat size or inventory to satisfy hard chemistry constraints.",
            ]

    cost_insights = [
        "High-cost alloy additions (FeCr/FeMo/FeSi/FeMn) are typically required to satisfy alloy minimums.",
        "Lower-cost scraps can reduce cost but may increase tramp or miss alloy windows.",
    ]
    if tramp_warnings:
        cost_insights.append(f"Tramp risk flagged: {tramp_warnings[0]}")

    return {
        "advisor_summary": summary,
        "advisor_actions": actions,
        "advisor_cost_insights": cost_insights,
    }


def _extract_json(text: str) -> Dict | None:
    if not text:
        return None
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:  # noqa: BLE001
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except Exception:  # noqa: BLE001
            return None
    return None


def generate_actionable_advice(
    request_payload: Dict,
    optimize_result: Dict,
    scrap_config: Dict,
) -> Dict[str, List[str] | str]:
    fallback = _fallback_actions(optimize_result)

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("OPENAI_MODEL", "gpt-5.2").strip()
    if not api_key or OpenAI is None:
        return fallback

    try:
        client = OpenAI(api_key=api_key)
        prompt_payload = {
            "objective": "Give actionable melt-shop recommendations from optimization result.",
            "rules": [
                "Be concise and operational.",
                "Return strict JSON only.",
                "Include actionable next steps for infeasible status.",
                "Include cost analysis levers.",
                "Do not include disclaimers.",
            ],
            "request": request_payload,
            "optimization_result": optimize_result,
            "scrap_costs": {
                name: item.get("cost_inr_per_ton", 0.0)
                for name, item in scrap_config.get("scrap_grades", {}).items()
            },
            "output_schema": {
                "advisor_summary": "string",
                "advisor_actions": ["string"],
                "advisor_cost_insights": ["string"],
            },
        }

        response = client.responses.create(
            model=model,
            input=[
                {
                    "role": "system",
                    "content": "You are a steel melt-shop optimization copilot. Return JSON only.",
                },
                {"role": "user", "content": json.dumps(prompt_payload)},
            ],
        )
        raw_text = getattr(response, "output_text", "") or ""
        parsed = _extract_json(raw_text)
        if not parsed:
            return fallback

        summary = str(parsed.get("advisor_summary", "")).strip()
        actions = parsed.get("advisor_actions", [])
        cost_insights = parsed.get("advisor_cost_insights", [])

        if not isinstance(actions, list):
            actions = []
        if not isinstance(cost_insights, list):
            cost_insights = []

        clean_actions = [str(x).strip() for x in actions if str(x).strip()]
        clean_cost = [str(x).strip() for x in cost_insights if str(x).strip()]

        if not summary:
            return fallback

        return {
            "advisor_summary": summary,
            "advisor_actions": clean_actions[:6] or fallback["advisor_actions"],
            "advisor_cost_insights": clean_cost[:6] or fallback["advisor_cost_insights"],
        }
    except Exception:  # noqa: BLE001
        return fallback

