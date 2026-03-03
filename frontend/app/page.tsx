"use client";

import { ChangeEvent, useEffect, useMemo, useState } from "react";

import { ConfigResponse, OptimizeResponse } from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type RowState = {
  available_tons: number;
  std_dev_cu: number;
  std_dev_sn: number;
  cost_inr_per_ton: number;
};

const DEFAULT_FEASIBLE_GRADE = "SAE 4140";
const DEFAULT_FEASIBLE_HEAT_SIZE = 30;
const DEFAULT_FEASIBLE_ROWS: Record<
  string,
  { available_tons?: number; std_dev_cu?: number; std_dev_sn?: number }
> = {
  "HMS-1": { available_tons: 80, std_dev_cu: 0.015, std_dev_sn: 0.0020 },
  "HMS-2": { available_tons: 70, std_dev_cu: 0.020, std_dev_sn: 0.0015 },
  "Shredded Scrap": { available_tons: 60, std_dev_cu: 0.010, std_dev_sn: 0.0010 },
  Turnings: { available_tons: 25, std_dev_cu: 0.030, std_dev_sn: 0.0020 },
  "Auto Scrap": { available_tons: 2, std_dev_cu: 0.120, std_dev_sn: 0.0040 },
  "Pig Iron": { available_tons: 40, std_dev_cu: 0.003, std_dev_sn: 0.0005 },
  DRI: { available_tons: 120, std_dev_cu: 0.001, std_dev_sn: 0.0002 },
  FeCr_LC: { available_tons: 2.0, std_dev_cu: 0.0, std_dev_sn: 0.0 },
  FeMo: { available_tons: 0.6, std_dev_cu: 0.0, std_dev_sn: 0.0 },
  FeSi: { available_tons: 0.25, std_dev_cu: 0.0, std_dev_sn: 0.0 },
  FeMn_HC: { available_tons: 0.8, std_dev_cu: 0.0, std_dev_sn: 0.0 }
};

export default function Home() {
  const [config, setConfig] = useState<ConfigResponse | null>(null);
  const [grade, setGrade] = useState<string>("");
  const [heatSize, setHeatSize] = useState<number>(DEFAULT_FEASIBLE_HEAT_SIZE);
  const [rows, setRows] = useState<Record<string, RowState>>({});
  const [result, setResult] = useState<OptimizeResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    const loadConfig = async () => {
      setError("");
      try {
        const res = await fetch(`${API_URL}/config`);
        if (!res.ok) {
          throw new Error("Failed to load backend config.");
        }
        const data: ConfigResponse = await res.json();
        setConfig(data);
        const defaultGrade =
          data.steel_grades[DEFAULT_FEASIBLE_GRADE] !== undefined
            ? DEFAULT_FEASIBLE_GRADE
            : (Object.keys(data.steel_grades)[0] ?? "");
        setGrade(defaultGrade);
        setHeatSize(DEFAULT_FEASIBLE_HEAT_SIZE);

        const initialRows: Record<string, RowState> = {};
        Object.entries(data.scrap_config.scrap_grades).forEach(([scrap, item]) => {
          const preset = DEFAULT_FEASIBLE_ROWS[scrap];
          initialRows[scrap] = {
            available_tons: preset?.available_tons ?? item.available_tons,
            std_dev_cu: preset?.std_dev_cu ?? (item.chemistry.Cu?.std_dev ?? 0),
            std_dev_sn: preset?.std_dev_sn ?? (item.chemistry.Sn?.std_dev ?? 0),
            cost_inr_per_ton: item.cost_inr_per_ton
          };
        });
        setRows(initialRows);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Config load failed.");
      }
    };
    void loadConfig();
  }, []);

  const gradeElements = useMemo(() => {
    if (!config || !grade) return [];
    return Object.keys(config.steel_grades[grade]).sort();
  }, [config, grade]);

  const handleRowChange = (scrap: string, field: keyof RowState, value: number) => {
    setRows((prev) => ({
      ...prev,
      [scrap]: {
        ...prev[scrap],
        [field]: Number.isFinite(value) ? value : 0
      }
    }));
  };

  const onUpload = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setError("");
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${API_URL}/upload_inventory`, {
        method: "POST",
        body: formData
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail ?? "Inventory upload failed.");
      }

      const latest = data.scrap_config?.scrap_grades ?? {};
      setRows((prev) => {
        const next = { ...prev };
        Object.keys(latest).forEach((scrap) => {
          next[scrap] = {
            ...next[scrap],
            available_tons: Number(latest[scrap].available_tons ?? 0),
            std_dev_cu: Number(latest[scrap].chemistry?.Cu?.std_dev ?? 0),
            std_dev_sn: Number(latest[scrap].chemistry?.Sn?.std_dev ?? 0),
            cost_inr_per_ton: Number(latest[scrap].cost_inr_per_ton ?? 0)
          };
        });
        return next;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Inventory upload failed.");
    }
  };

  const optimize = async () => {
    if (!grade) {
      setError("Select grade.");
      return;
    }
    setLoading(true);
    setError("");
    setResult(null);

    const inventory_tons: Record<string, number> = {};
    const std_dev_overrides: Record<string, Record<string, number>> = {};

    Object.entries(rows).forEach(([scrap, row]) => {
      inventory_tons[scrap] = Number(row.available_tons) || 0;
      std_dev_overrides[scrap] = {
        Cu: Number(row.std_dev_cu) || 0,
        Sn: Number(row.std_dev_sn) || 0
      };
    });

    try {
      const res = await fetch(`${API_URL}/optimize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          grade,
          heat_size_tons: heatSize,
          inventory_tons,
          std_dev_overrides
        })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail ?? "Optimization failed.");
      }
      setResult(data as OptimizeResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Optimization failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="mx-auto max-w-7xl p-4 md:p-6">
      <h1 className="mb-4 text-xl font-semibold tracking-wide text-accent">KSL EAF Scrap Mix Optimizer</h1>

      {error ? (
        <div className="mb-4 rounded border border-danger/50 bg-danger/10 px-3 py-2 text-sm text-danger">
          {error}
        </div>
      ) : null}

      <section className="grid gap-4 lg:grid-cols-[360px_1fr]">
        <div className="rounded border border-edge bg-panel p-4 shadow-sm">
          <label className="mb-2 block text-sm text-slate-600">Steel Grade</label>
          <select
            className="mb-3 w-full rounded border border-edge bg-panelAlt px-3 py-2"
            value={grade}
            onChange={(e) => setGrade(e.target.value)}
          >
            {config
              ? Object.keys(config.steel_grades).map((g) => (
                  <option key={g} value={g}>
                    {g}
                  </option>
                ))
              : null}
          </select>

          <label className="mb-2 block text-sm text-slate-600">Heat Size (tons)</label>
          <input
            className="mb-3 w-full rounded border border-edge bg-panelAlt px-3 py-2"
            type="number"
            min={1}
            step="0.1"
            value={heatSize}
            onChange={(e) => setHeatSize(Number(e.target.value))}
          />

          <label className="mb-2 block text-sm text-slate-600">Inventory Excel</label>
          <input
            className="mb-4 block w-full cursor-pointer rounded border border-edge bg-panelAlt px-3 py-2 text-sm"
            type="file"
            accept=".xlsx,.xls,.xlsm"
            onChange={onUpload}
          />

          <button
            className="w-full rounded bg-accent px-4 py-2 font-semibold text-white disabled:opacity-50"
            onClick={optimize}
            disabled={loading}
          >
            {loading ? "Optimizing..." : "Optimize Mix"}
          </button>
        </div>

        <div className="rounded border border-edge bg-panel p-4 shadow-sm">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-600">Scrap Inventory</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-edge text-slate-600">
                  <th className="px-2 py-2 text-left">Scrap</th>
                  <th className="px-2 py-2 text-right">Available (t)</th>
                  <th className="px-2 py-2 text-right">Cu Std Dev</th>
                  <th className="px-2 py-2 text-right">Sn Std Dev</th>
                  <th className="px-2 py-2 text-right">Cost (INR/t)</th>
                </tr>
              </thead>
              <tbody>
                {Object.keys(rows).map((scrap) => (
                  <tr key={scrap} className="border-b border-edge/40">
                    <td className="px-2 py-2">{scrap}</td>
                    <td className="px-2 py-2">
                      <input
                        className="w-full rounded border border-edge bg-panelAlt px-2 py-1 text-right"
                        type="number"
                        step="0.1"
                        value={rows[scrap].available_tons}
                        onChange={(e) =>
                          handleRowChange(scrap, "available_tons", Number(e.target.value))
                        }
                      />
                    </td>
                    <td className="px-2 py-2">
                      <input
                        className="w-full rounded border border-edge bg-panelAlt px-2 py-1 text-right"
                        type="number"
                        step="0.001"
                        value={rows[scrap].std_dev_cu}
                        onChange={(e) => handleRowChange(scrap, "std_dev_cu", Number(e.target.value))}
                      />
                    </td>
                    <td className="px-2 py-2">
                      <input
                        className="w-full rounded border border-edge bg-panelAlt px-2 py-1 text-right"
                        type="number"
                        step="0.001"
                        value={rows[scrap].std_dev_sn}
                        onChange={(e) => handleRowChange(scrap, "std_dev_sn", Number(e.target.value))}
                      />
                    </td>
                    <td className="px-2 py-2 text-right">{rows[scrap].cost_inr_per_ton.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {result ? (
        <section className="mt-4 grid gap-4 lg:grid-cols-2">
          <div className="rounded border border-edge bg-panel p-4 shadow-sm">
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-slate-600">Optimization Result</h2>
            <div className={`mb-3 rounded px-3 py-2 text-sm ${result.feasible ? "bg-ok/15 text-ok" : "bg-danger/15 text-danger"}`}>
              Status: {result.status} ({result.feasible ? "Feasible" : "Infeasible"})
            </div>
            <div className="mb-2 text-sm">Total Cost: INR {result.total_cost_inr.toLocaleString(undefined, { maximumFractionDigits: 0 })}</div>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-edge text-slate-600">
                  <th className="px-2 py-2 text-left">Scrap</th>
                  <th className="px-2 py-2 text-right">Tons</th>
                  <th className="px-2 py-2 text-right">Cost (INR)</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(result.mix_tons).map(([scrap, tons]) => (
                  <tr key={scrap} className="border-b border-edge/40">
                    <td className="px-2 py-2">{scrap}</td>
                    <td className="px-2 py-2 text-right">{tons.toFixed(3)}</td>
                    <td className="px-2 py-2 text-right">
                      {Math.round((rows[scrap]?.cost_inr_per_ton ?? 0) * tons).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="rounded border border-edge bg-panel p-4 shadow-sm">
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-slate-600">Chemistry Check</h2>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-edge text-slate-600">
                  <th className="px-2 py-2 text-left">Element</th>
                  <th className="px-2 py-2 text-right">Target</th>
                  <th className="px-2 py-2 text-right">Predicted</th>
                  <th className="px-2 py-2 text-right">Safe</th>
                </tr>
              </thead>
              <tbody>
                {gradeElements.map((el) => {
                  const bounds = config?.steel_grades[grade]?.[el] ?? {};
                  const target =
                    bounds.min !== undefined && bounds.max !== undefined
                      ? `${bounds.min}-${bounds.max}`
                      : bounds.min !== undefined
                        ? `>= ${bounds.min}`
                        : `<= ${bounds.max}`;
                  return (
                    <tr key={el} className="border-b border-edge/40">
                      <td className="px-2 py-2">{el}</td>
                      <td className="px-2 py-2 text-right">{target}</td>
                      <td className="px-2 py-2 text-right">{(result.predicted_chemistry[el] ?? 0).toFixed(4)}</td>
                      <td className="px-2 py-2 text-right">{(result.safe_chemistry[el] ?? 0).toFixed(4)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            {result.tramp_warnings.length > 0 ? (
              <div className="mt-3 rounded border border-danger/50 bg-danger/10 p-3 text-xs text-danger">
                {result.tramp_warnings.map((w) => (
                  <div key={w}>{w}</div>
                ))}
              </div>
            ) : null}

            {result.violations.length > 0 ? (
              <div className="mt-3 rounded border border-danger/50 bg-danger/10 p-3 text-xs text-danger">
                {result.violations.map((v) => (
                  <div key={v}>{v}</div>
                ))}
              </div>
            ) : null}

            {result.suggestions.length > 0 ? (
              <div className="mt-3 rounded border border-accent/30 bg-accent/10 p-3 text-xs text-accent">
                {result.suggestions.map((s) => (
                  <div key={s}>{s}</div>
                ))}
              </div>
            ) : null}
          </div>
        </section>
      ) : null}

      {result ? (
        <section className="mt-4 rounded border border-edge bg-panel p-4 shadow-sm">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-slate-600">Actionable Advisor</h2>
          <div className="mb-3 rounded border border-edge bg-panelAlt p-3 text-sm">{result.advisor_summary}</div>

          <div className="grid gap-3 lg:grid-cols-2">
            <div className="rounded border border-edge bg-panelAlt p-3 text-sm">
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-600">Actions</h3>
              {result.advisor_actions.length > 0 ? (
                <ul className="list-disc space-y-1 pl-5">
                  {result.advisor_actions.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              ) : (
                <div>No actions returned.</div>
              )}
            </div>

            <div className="rounded border border-edge bg-panelAlt p-3 text-sm">
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-600">Cost Insights</h3>
              {result.advisor_cost_insights.length > 0 ? (
                <ul className="list-disc space-y-1 pl-5">
                  {result.advisor_cost_insights.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              ) : (
                <div>No cost insights returned.</div>
              )}
            </div>
          </div>
        </section>
      ) : null}
    </main>
  );
}
