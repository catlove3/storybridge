export type Level = 'high' | 'medium' | 'low'

export type NodeKind =
  | 'character'
  | 'scene'
  | 'event'
  | 'setting'
  | 'culture_mechanism'
  | 'commitment'

export type EdgeRelation =
  | 'appears_in'
  | 'motivates'
  | 'causes'
  | 'depends_on'
  | 'references'
  | 'reveals'
  | 'conflicts_with'
  | 'sets_up'
  | 'pays_off'

export type PlotFunction =
  | 'motivation'
  | 'constraint'
  | 'conflict'
  | 'revelation'
  | 'foreshadowing'
  | 'payoff'
  | 'reversal'

export type SocialFunction =
  | 'status'
  | 'power'
  | 'obligation'
  | 'kinship'
  | 'reputation'
  | 'institutional_access'
  | 'economic_security'

export type EmotionalFunction =
  | 'humiliation'
  | 'aspiration'
  | 'fear'
  | 'sympathy'
  | 'suspense'
  | 'satisfaction'

export interface FunctionTags {
  plot: PlotFunction[]
  social: SocialFunction[]
  emotional: EmotionalFunction[]
}

export interface Character {
  id: string
  name: string
  role: 'protagonist' | 'antagonist' | 'supporting' | 'minor'
  description: string
  goals: string[]
}

export interface Scene {
  id: string
  title: string
  summary: string
  text: string
  character_ids: string[]
  event_ids: string[]
}

export interface StoryEvent {
  id: string
  description: string
  scene_ids: string[]
}

export interface Setting {
  id: string
  name: string
  description: string
}

export interface CultureMechanism {
  id: string
  name: string
  description: string
  surface_text: string[]
  scene_ids: string[]
  friction_level: Level
  narrative_importance: Level
  functions: FunctionTags
  adapted_to: string | null
  adapted_strategy: string | null
}

export interface Commitment {
  id: string
  description: string
  established_at_scene_id: string | null
  payoff_scene_id: string | null
  must_preserve: boolean
}

export interface Dependency {
  source_id: string
  target_id: string
  relation: EdgeRelation
  evidence: string
  confidence: number
}

export interface StoryState {
  version: number
  target_market: string
  audience: string
  format: string
  genre: string
  source_language: string
  target_language: string
  target_locale: string
  style_guide: string
  terminology_map: Record<string, string>
  characters: Character[]
  scenes: Scene[]
  events: StoryEvent[]
  settings: Setting[]
  culture_mechanisms: CultureMechanism[]
  commitments: Commitment[]
  dependencies: Dependency[]
}

export interface TargetScene {
  id: string
  title: string
  summary: string
  text: string
}

export interface TargetScript {
  source_state_version: number
  source_language: string
  target_language: string
  target_locale: string
  scenes: TargetScene[]
}

export interface Revision {
  revision_id: number
  state_version: number
  created_at: string
  kind: 'initial_parse' | 'friction_detection' | 'adaptation_applied' | 'repair'
  description: string
  changed_scene_ids: string[]
  applied_option: Record<string, unknown> | null
}

export interface MechanismFriction {
  id: string
  friction_level: Level
  narrative_importance: Level
  functions: FunctionTags
  drop: boolean
}

export interface FrictionDetectionResult {
  mechanisms: MechanismFriction[]
}

export type AdaptationStrategy =
  | 'preserve'
  | 'functional_replacement'
  | 'plot_reconstruction'

export type ImpactKind =
  | 'direct_reference'
  | 'motivation'
  | 'causal'
  | 'payoff'
  | 'structural'

export interface AffectedScene {
  scene_id: string
  impact_kinds: ImpactKind[]
  reason_path: string[]
  evidence: string
  path_confidence: number
}

export interface PropagationResult {
  changed_node_id: string
  affected_scenes: AffectedScene[]
  related_commitment_ids: string[]
  summary: string
}

export interface AdaptationOption {
  option_label: string
  strategy: AdaptationStrategy
  title: string
  replacement_definition: string
  rationale: string
  preserved_functions: string[]
  lost_functions: string[]
  risks: string[]
}

export interface AdaptationPlan {
  culture_mechanism_id: string
  original_name: string
  based_on_version: number
  friction_level: Level
  options: AdaptationOption[]
}

export interface AppliedAdaptation {
  plan_culture_mechanism_id: string
  state_version: number
  operation_id: string | null
  chosen_option: AdaptationOption
  propagation: PropagationResult
  rewritten_scene_ids: string[]
  notes: string
}

export interface RewrittenScene {
  id: string
  title: string
  summary: string
  text: string
}

export type IssueType =
  | 'stale_reference'
  | 'fact_conflict'
  | 'motivation_break'
  | 'commitment_violation'
  | 'unresolved_payoff'

export type Severity = 'error' | 'warning' | 'info'

export interface VerificationIssue {
  issue_type: IssueType
  severity: Severity
  scene_id: string | null
  description: string
  evidence: string
}

export interface CommitmentCheck {
  commitment_id: string
  status: 'preserved' | 'violated' | 'needs_review'
  explanation: string
}

export interface VerifyReport {
  issues: VerificationIssue[]
  commitment_checks: CommitmentCheck[]
  checked_scene_ids: string[]
  static_checks_passed: number
  static_checks_total: number
  commitments_verified: number
  commitments_total: number
  scenes_checked: number
  scenes_total: number
  overall_status: 'not_run' | 'pass' | 'needs_review' | 'fail'
  consistency_score: number
}

export interface MarketProfile {
  market: string
  audience: string
  format: string
  genre: string
  source_language?: string
  target_language?: string
  target_locale?: string
  style_guide?: string
  terminology_map?: Record<string, string>
}

export interface DataPolicy {
  sft_opt_in: boolean
  content_source: string
  license: string
  consent_note: string
  retention_days: number
}

export interface CreateProjectRequest {
  name: string
  script: string
  market: MarketProfile
  data_policy?: DataPolicy
}

export interface RuntimePolicy {
  authentication_required: boolean
  provider_endpoint: string
  model: string
  sft_collection_enabled: boolean
  sft_redaction_enabled: boolean
  sft_retention_days: number
  max_script_chars: number
  max_project_llm_tokens: number
}

export interface CreateProjectResponse {
  id: string
  name: string
}

export interface ProjectSummary {
  id: string
  name: string
  created_at: string
}

export interface ProjectDetail extends CreateProjectResponse {
  market: MarketProfile
  analyzed: boolean
  data_policy: DataPolicy
}

export type JobKind =
  | 'analyze'
  | 'plan'
  | 'apply'
  | 'plan_batch'
  | 'apply_batch'
  | 'verify'
  | 'render'
export type JobStatus = 'queued' | 'running' | 'done' | 'failed' | 'cancelled'

export interface AdaptationSelection {
  culture_mechanism_id: string
  option_label: 'A' | 'B' | 'C'
}

export interface SubmitJobRequest {
  kind: JobKind
  culture_mechanism_id?: string
  option_label?: string
  culture_mechanism_ids?: string[]
  adaptations?: AdaptationSelection[]
  based_on_version?: number
  idempotency_key?: string
}

export interface SubmitJobResponse {
  job_id: string
  status: JobStatus
}

export interface Job<TResult = unknown> {
  id: string
  kind: JobKind
  project_id: string
  status: JobStatus
  created_at: number
  finished_at: number | null
  result: TResult | null
  error: string | null
  idempotency_key: string | null
  progress: number
  cancel_requested: boolean
}

export interface GraphNode {
  id: string
  kind: NodeKind
  label: string
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  relation: EdgeRelation
  evidence: string
  confidence: number
}

export interface StoryGraphResponse {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface SceneDiff {
  scene_id: string
  before: string
  after: string
  diff: string[]
}

export interface ApplyResult {
  applied: AppliedAdaptation
  report: VerifyReport
  repair_rounds: number
  repaired_scene_ids: string[]
}

export interface BatchApplyResult {
  applied: AppliedAdaptation[]
  report: VerifyReport
  repair_rounds: number
  repaired_scene_ids: string[]
  from_version: number
  to_version: number
}
