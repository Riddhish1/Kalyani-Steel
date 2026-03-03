# KSL Scrap Mix Optimization System

Production-focused scrap mix optimization for:
- Kalyani Steels Limited (KSL)
- Saarloha Advanced Materials (Mundhwa, Pune)
- 30T EAF + LF/VD route

This implementation provides:
- FastAPI backend (`Python 3.11`) with PuLP linear optimization
- Next.js + TypeScript + Tailwind light industrial operator UI
- Cu/Sn uncertainty safety margin (`mean + 2*std_dev`)
- Heat feedback back-fitting with EMA
- Inventory Excel upload
- OpenAI-powered actionable advisor (with deterministic fallback)

## Repository Structure

```text
backend/
  main.py
  models.py
  optimizer.py
  requirements.txt
  create_inventory_template.py
  data/
    scrap_config.json
    steel_grades.json
    sample_optimize_request_4140_30t.json
frontend/
  app/
  package.json
  tailwind.config.ts
```

## Metallurgical Data Included

- Steel grades with exact chemistry windows:
  - SAE 4140, SAE 4340, SAE 8620, 20MnCr5, 42CrMo4, 100Cr6
- Scrap dataset with exact chemistry/cost from prompt:
  - HMS-1, HMS-2, Shredded Scrap, Turnings (yield factor 0.75), Auto Scrap, Pig Iron, DRI
- Recovery coefficients:
  - C 0.85, Mn 0.90, Si 0.30, Cr 0.70, Mo 0.85, Ni 0.90, Cu 1.00, Sn 1.00, P 0.95, S 0.90

## LP Formulation (Implemented)

Decision variables:
- `x_i` = tons of scrap grade `i`

Objective:
- Minimize `Σ c_i * x_i`

Constraints:
- Mass: `Σ x_i = W`
- Element bounds:
  - `W * Cj_min <= Σ (x_i * chem_ij * recovery_j * yield_i) <= W * Cj_max`
- Tramp constraints:
  - Cu and Sn upper bounds enforced
  - Cu/Sn in optimization use `mean + 2*std_dev`
- Inventory:
  - `0 <= x_i <= available_i`

## API Endpoints

- `GET /health`
- `GET /config`
- `POST /optimize`
- `POST /upload_inventory` (Excel)
- `POST /update_heat_feedback`

`POST /optimize` now also returns:
- `advisor_summary`
- `advisor_actions`
- `advisor_cost_insights`

### `POST /optimize` Example

Use [`backend/data/sample_optimize_request_4140_30t.json`](/Users/harshchaudhari/Documents/Kalyani Steel/backend/data/sample_optimize_request_4140_30t.json).

```bash
curl -X POST http://localhost:8000/optimize \
  -H "Content-Type: application/json" \
  -d @backend/data/sample_optimize_request_4140_30t.json
```

### `POST /update_heat_feedback` Example

```bash
curl -X POST http://localhost:8000/update_heat_feedback \
  -H "Content-Type: application/json" \
  -d '{
    "mix_tons": {"DRI": 10, "Pig Iron": 5, "HMS-2": 15},
    "predicted_chemistry": {"C": 0.40, "Mn": 0.80, "Cu": 0.06},
    "actual_tapped_chemistry": {"C": 0.42, "Mn": 0.76, "Cu": 0.07},
    "alpha": 0.1
  }'
```

## Excel Template Structure

Required columns:
- `scrap_grade`
- `available_tons`
- `std_dev_cu`
- `std_dev_sn`

Generate the template:

```bash
cd backend
python3 create_inventory_template.py
```

Output:
- `backend/data/inventory_template.xlsx`

## Run Locally

Optional AI advisor config (backend):

```bash
cd backend
cp .env.example .env
# set OPENAI_API_KEY and optionally OPENAI_MODEL (default gpt-5.2)
```

## 1) Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 create_inventory_template.py
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 2) Frontend

```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

Open:
- `http://localhost:3000`

## Deployment Notes

- Backend: deploy with Gunicorn/Uvicorn workers behind Nginx.
- Frontend: deploy Next.js on Vercel or Node runtime.
- Persist `backend/data/scrap_config.json` on durable storage, because EMA updates modify this file.

## Sample Test Case (SAE 4140, 30T Heat)

Input file:
- [`sample_optimize_request_4140_30t.json`](/Users/harshchaudhari/Documents/Kalyani Steel/backend/data/sample_optimize_request_4140_30t.json)

Run:
- `POST /optimize` with that payload.

Expected behavior:
- Returns LP feasibility status, mix, predicted chemistry, cost, and warnings/suggestions.
- If infeasible, response includes violated element(s) and corrective actions.

## Important Metallurgical Note

Given the exact provided scrap chemistry dataset, Cr/Mo/Ni-bearing grades can become infeasible if alloy-bearing charge sources are unavailable. The backend reports infeasibility with violation diagnostics and corrective suggestions instead of forcing non-physical solutions.
