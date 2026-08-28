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
  target_market: string
  audience: string
  format: string
  genre: string
  characters: Character[]
  scenes: Scene[]
  events: StoryEvent[]
  settings: Setting[]
  culture_mechanisms: CultureMechanism[]
  commitments: Commitment[]
  dependencies: Dependency[]
}

export interface Revision {
  revision_id: number
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
  friction_level: Level
  options: AdaptationOption[]
}

export interface AppliedAdaptation {
  plan_culture_mechanism_id: string
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
}

export interface CreateProjectRequest {
  name: string
  script: string
  market: MarketProfile
}

export interface CreateProjectResponse {
  id: string
  name: string
}

export type JobKind = 'analyze' | 'plan' | 'apply' | 'verify'
export type JobStatus = 'running' | 'done' | 'failed'

export interface SubmitJobRequest {
  kind: JobKind
  culture_mechanism_id?: string
  option_label?: string
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
}

export interface GraphNode {
  id: string
  kind: NodeKind
  label: string
}

export interface GraphEdge {
  source: string
  target: string
  relation: EdgeRelation
  evidence: string
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
