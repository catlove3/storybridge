import type { components } from '../api/generated/schema'

type Schema<Name extends keyof components['schemas']> = components['schemas'][Name]
type WithDefaults<T, Keys extends keyof T> = Omit<T, Keys> & Required<Pick<T, Keys>>

export type Level = Schema<'Level'>
export type NodeKind = Schema<'NodeKind'>
export type EdgeRelation = Schema<'EdgeRelation'>
export type PlotFunction = Schema<'PlotFunction'>
export type SocialFunction = Schema<'SocialFunction'>
export type EmotionalFunction = Schema<'EmotionalFunction'>
export type AdaptationStrategy = Schema<'AdaptationStrategy'>
export type ImpactKind = Schema<'ImpactKind'>
export type IssueType = Schema<'IssueType'>
export type Severity = Schema<'Severity'>
export type JobKind = Schema<'JobKind'>
export type JobStatus = Schema<'JobStatus'>

export type FunctionTags = WithDefaults<
  Schema<'FunctionTags'>,
  'plot' | 'social' | 'emotional'
>
export type Character = WithDefaults<Schema<'Character'>, 'goals'>
export type Scene = WithDefaults<Schema<'Scene'>, 'character_ids' | 'event_ids'>
export type StoryEvent = WithDefaults<Schema<'Event'>, 'scene_ids'>
export type Setting = Schema<'Setting'>
export type CultureMechanism = Omit<
  WithDefaults<Schema<'CultureMechanism'>, 'surface_text' | 'scene_ids' | 'functions'>,
  'functions'
> & { functions: FunctionTags }
export type Commitment = Schema<'Commitment'>
export type Dependency = Schema<'Dependency'>

export type StoryState = Omit<
  WithDefaults<
    Schema<'StoryState'>,
    | 'terminology_map'
    | 'characters'
    | 'scenes'
    | 'events'
    | 'settings'
    | 'culture_mechanisms'
    | 'commitments'
    | 'dependencies'
  >,
  'characters' | 'scenes' | 'events' | 'culture_mechanisms'
> & {
  characters: Character[]
  scenes: Scene[]
  events: StoryEvent[]
  culture_mechanisms: CultureMechanism[]
}

export type TargetScene = Schema<'TargetScene'>
export type TargetScript = Schema<'TargetScript'>
export type Revision = WithDefaults<
  Schema<'Revision'>,
  'created_at' | 'changed_scene_ids' | 'applied_option'
>
export type AffectedScene = WithDefaults<Schema<'AffectedScene'>, 'reason_path'>
export type PropagationResult = Omit<
  WithDefaults<Schema<'PropagationResult'>, 'related_commitment_ids'>,
  'affected_scenes'
> & { affected_scenes: AffectedScene[] }
export type AdaptationOption = WithDefaults<
  Schema<'AdaptationOption'>,
  'preserved_functions' | 'lost_functions' | 'risks'
>
export type AdaptationPlan = Omit<Schema<'AdaptationPlan'>, 'options'> & {
  options: AdaptationOption[]
}
export type AppliedAdaptation = Omit<Schema<'AppliedAdaptation'>, 'chosen_option' | 'propagation'> & {
  chosen_option: AdaptationOption
  propagation: PropagationResult
}
export type RewrittenScene = Scene
export type VerificationIssue = Schema<'VerificationIssue'>
export type CommitmentCheck = Schema<'CommitmentCheck'>
export type VerifyReport = WithDefaults<
  Schema<'VerifyReport'>,
  'issues' | 'commitment_checks' | 'checked_scene_ids'
>

export type MarketProfile = Schema<'MarketProfile'>
export type DataPolicy = Schema<'DataPolicy'>
export type CreateProjectRequest = Schema<'CreateProjectBody'>
export type RuntimePolicy = Schema<'RuntimePolicyResponse'>
export type CreateProjectResponse = Schema<'ProjectCreated'>
export type ProjectSummary = Schema<'ProjectSummary'>
export type ProjectDetail = Schema<'ProjectDetail'>
export type AdaptationSelection = Schema<'AdaptationSelection'>
export type SubmitJobRequest = Schema<'JobSubmitBody'>
export type SubmitJobResponse = Schema<'JobSubmitted'>

export type Job<TResult = unknown> = Omit<Schema<'JobResponse'>, 'result'> & {
  result: TResult | null
}

export type GraphNode = Schema<'GraphNode'>
export type GraphEdge = Schema<'GraphEdge'>
export type StoryGraphResponse = Schema<'StoryGraphResponse'>
export type SceneDiff = Schema<'SceneDiffResponse'>
export type ApplyResult = Omit<Schema<'ApplyResult'>, 'applied' | 'report'> & {
  applied: AppliedAdaptation
  report: VerifyReport
}
export type BatchApplyResult = Omit<Schema<'BatchApplyResult'>, 'applied' | 'report'> & {
  applied: AppliedAdaptation[]
  report: VerifyReport
}
