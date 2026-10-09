export type Severity = 'Critical' | 'Warning' | 'Info'

export type GTINType =
  | 'GTIN-8'
  | 'GTIN-12 (UPC-A)'
  | 'GTIN-13 (EAN)'
  | 'GTIN-14 (ITF-14)'
  | 'Unknown'

export interface Issue {
  severity: Severity
  code: string
  message: string
  recommendation: string
  retailer_impact: string
}

export interface GTINResult {
  raw_input: string
  cleaned: string
  row_number: number
  is_valid: boolean
  gtin_type: GTINType
  issues: Issue[]
  corrected_value: string | null
  company_prefix: string | null
  indicator_digit: string | null
  check_digit_expected: string | null
  has_critical: boolean
  has_warning: boolean
}

export interface BatchSummary {
  total_gtins: number
  valid: number
  critical_issues: number
  warnings: number
  clean: number
  duplicate_groups: number
  unique_prefixes: number
}

export interface ScoreResult {
  score: number
  grade: string
  interpretation: string
}

export interface CostAssumptions {
  chargeback_per_item_low: number
  chargeback_per_item_high: number
  delayed_launch_per_sku_low: number
  delayed_launch_per_sku_high: number
  delayed_sku_fraction: number
  rework_rate_per_hour: number
  rework_hours_per_critical: number
  rework_hours_per_warning: number
  growth_multiplier_low: number
  growth_multiplier_high: number
}

export interface CostDrivers {
  critical_count: number
  warning_count: number
  total_gtins: number
  delayed_skus: number
  rework_hours: number
}

export interface CostEstimate {
  chargeback_range: [number, number]
  delayed_launch_range: [number, number]
  rework_hours: number
  rework_cost: number
  annual_estimate_low: number
  annual_estimate_high: number
  growth_note: string
  delayed_skus: number
  assumptions: CostAssumptions
  drivers: CostDrivers
}

export interface HierarchyPair {
  case_gtin: string
  case_row: number
  unit_gtin: string
  unit_row: number
  indicator: string
}

export interface HierarchyAnalysis {
  matched_pairs: HierarchyPair[]
  orphan_cases: GTINResult[]
  units_without_cases: GTINResult[]
  has_hierarchy: boolean
  hierarchy_complete: boolean
}

export interface RetailerCheck {
  check: string
  passed: boolean
  detail: string
  failing_gtins: [number, string][]
}

export interface RetailerChecklist {
  profile: { description: string; notes: string }
  checks: RetailerCheck[]
  passed: number
  total: number
  ready: boolean
}

export interface BeforeAfter {
  row: number
  before: string
  after: string
  issue: string
}

export interface FixRoadmapItem {
  priority: number
  code: string
  action: string
  count: number
  severity: string
  effort: string
  effort_detail: string
  impact: string
  impact_detail: string
  time_estimate: string
}

export interface GTIN14Indicator {
  gtin14: string
  label: string
}

export interface GTIN14Suggestion {
  row: number
  unit_gtin: string
  unit_type: string
  indicators: Record<number, GTIN14Indicator>
}

export interface FieldAnalysis {
  column_name: string
  total_rows: number
  populated: number
  missing: number
  completeness_pct: number
}

export interface RetailerDataGap {
  required: number
  present: number
  missing_fields: string[]
  incomplete_fields: string[]
  ready: boolean
}

export interface DataCompleteness {
  field_analysis: Record<string, FieldAnalysis>
  missing_important_fields: string[]
  retailer_data_gaps: Record<string, RetailerDataGap>
  overall_completeness: number
}

export interface ValidationResponse {
  token: string
  results: GTINResult[]
  summary: BatchSummary
  duplicates: Record<string, number>
  hierarchy: HierarchyAnalysis
  retailer_checklists: Record<string, RetailerChecklist>
  score: ScoreResult
  cost_estimate: CostEstimate | null
  executive_summary: string
  fix_roadmap: FixRoadmapItem[]
  before_after: BeforeAfter[]
  gtin14_suggestions: GTIN14Suggestion[]
}

// Own-data result: score and issue counts only. No rows, no token.
export interface SummaryResponse {
  summary: BatchSummary
  score: ScoreResult
}

export function isFullReport(
  data: ValidationResponse | SummaryResponse,
): data is ValidationResponse {
  return 'token' in data
}

export interface SampleData {
  csv: string
  description: string
}

export interface ParsedFile {
  fileName: string
  columns: string[]
  detectedGtinColumn: string | null
  selectedGtinColumn: string
  rowCount: number
  previewRows: Record<string, string>[]
  gtins: string[]
}

export type Phase = 'idle' | 'loading' | 'results'

export type InputMethod = 'upload' | 'sample' | null

export interface AppState {
  phase: Phase
  inputMethod: InputMethod
  parsedFile: ParsedFile | null
  validationData: ValidationResponse | SummaryResponse | null
  companyName: string
  selectedRetailer: string
  activeSection: string
  error: string | null
}

export type AppAction =
  | { type: 'SET_INPUT_METHOD'; method: InputMethod }
  | { type: 'FILE_PARSED'; payload: ParsedFile }
  | { type: 'VALIDATION_START' }
  | { type: 'VALIDATION_SUCCESS'; data: ValidationResponse | SummaryResponse }
  | { type: 'VALIDATION_ERROR'; error: string }
  | { type: 'START_OVER' }
  | { type: 'SET_COMPANY_NAME'; name: string }
  | { type: 'SET_RETAILER'; retailer: string }
  | { type: 'SET_ACTIVE_SECTION'; section: string }
  | { type: 'SET_COLUMN'; column: string }
