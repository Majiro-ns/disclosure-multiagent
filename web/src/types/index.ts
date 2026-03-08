export interface CompanyInfo {
  edinet_code: string;
  sec_code: string;
  company_name: string;
  company_name_en: string;
  industry: string;
  listing: string;
}

export interface EdinetDocument {
  doc_id: string;
  edinet_code: string;
  filer_name: string;
  doc_type_code: string;
  period_end: string;
  submit_date_time: string;
}

export interface GapItem {
  gap_id: string;
  section_heading: string;
  change_type: string;
  has_gap: boolean | null;
  disclosure_item: string;
  reference_law_title: string;
  reference_url: string;
  evidence_hint: string;
  confidence: string;
  gap_description?: string;
}

export interface NoGapItem {
  disclosure_item: string;
  reference_law_id: string;
  evidence_hint: string;
}

export interface GapSummary {
  total_gaps: number;
  by_change_type: Record<string, number>;
}

export interface Proposal {
  level: string;
  text: string;
  char_count: number;
  status: string;
}

export interface ProposalSet {
  gap_id: string;
  disclosure_item: string;
  reference_law_id: string;
  matsu: Proposal;
  take: Proposal;
  ume: Proposal;
}

export interface AnalysisResult {
  company_name: string;
  fiscal_year: number;
  level: string;
  summary: GapSummary;
  gaps: GapItem[];
  no_gap_items: NoGapItem[];
  proposals: ProposalSet[];
  report_markdown: string;
}

export interface PipelineStep {
  step: number;
  name: string;
  status: 'pending' | 'running' | 'done' | 'error';
  detail: string;
}

export interface PipelineStatus {
  task_id: string;
  status: 'queued' | 'running' | 'done' | 'error';
  current_step: number;
  steps: PipelineStep[];
  result: AnalysisResult | null;
  error: string | null;
}

// ── Step Execution API Types ──────────────────────────────

export interface M1Section {
  heading: string;
  text_excerpt: string;
  char_count: number;
}

export interface M1StepOutput {
  company_name: string;
  section_count: number;
  sections: M1Section[];
}

export interface M2LawEntry {
  id: string;
  title: string;
  category: string;
  source_confirmed: boolean | null;
  warning?: string;
}

export interface M2StepOutput {
  applied_count: number;
  warning_count: number;
  entries: M2LawEntry[];
}

export interface M3StepOutput {
  total_gaps: number;
  by_change_type: Record<string, number>;
  gaps: GapItem[];
}

export interface M4StepOutput {
  proposals: ProposalSet[];
}

export interface M5StepOutput {
  report_markdown: string;
}

export interface StepOutputsMap {
  m1?: M1StepOutput;
  m2?: M2StepOutput;
  m3?: M3StepOutput;
  m4?: M4StepOutput;
  m5?: M5StepOutput;
}

export interface StepStartResponse {
  task_id: string;
  status: string;
  next_stage: string;
  m1_output: M1StepOutput;
}

export type StepNextStatus = 'done' | 'waiting_debug' | 'all_done';

export interface StepNextResponse {
  task_id: string;
  step: 'm1' | 'm2' | 'm3' | 'm4' | 'm5';
  status: StepNextStatus;
  output: M1StepOutput | M2StepOutput | M3StepOutput | M4StepOutput | M5StepOutput | null;
}
