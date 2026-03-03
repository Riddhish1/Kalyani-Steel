export type Bound = {
  min?: number;
  max?: number;
};

export type SteelGrades = Record<string, Record<string, Bound>>;

export type ChemistryValue = {
  mean: number;
  std_dev: number;
};

export type ScrapGrade = {
  available_tons: number;
  cost_inr_per_ton: number;
  yield_factor: number;
  chemistry: Record<string, ChemistryValue>;
};

export type ScrapConfig = {
  scrap_grades: Record<string, ScrapGrade>;
};

export type ConfigResponse = {
  steel_grades: SteelGrades;
  scrap_config: ScrapConfig;
};

export type OptimizeResponse = {
  feasible: boolean;
  status: string;
  mix_tons: Record<string, number>;
  predicted_chemistry: Record<string, number>;
  safe_chemistry: Record<string, number>;
  total_cost_inr: number;
  violations: string[];
  suggestions: string[];
  tramp_warnings: string[];
  advisor_summary: string;
  advisor_actions: string[];
  advisor_cost_insights: string[];
};
