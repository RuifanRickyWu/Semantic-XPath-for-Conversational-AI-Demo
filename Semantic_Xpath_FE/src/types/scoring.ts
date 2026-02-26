export interface ScoredNodeMeta {
  type?: string;
  attributes?: Record<string, string | number | boolean | null | undefined>;
  [key: string]: unknown;
}

export interface NodeTestIndex {
  start?: number;
  end?: number;
  to_end?: boolean;
}

export interface NodeTestRelativeIndex {
  offset?: number;
}

export interface NodeTestLeaf {
  kind?: string;
  name?: string;
  index?: NodeTestIndex;
  predicate?: unknown;
  predicate_str?: string;
  relative_index?: NodeTestRelativeIndex;
}

export interface NodeTestExpr {
  type?: string;
  test?: NodeTestLeaf;
  children?: NodeTestExpr[];
  [key: string]: unknown;
}

export interface ScoringSubStep {
  type?: string;
  node_name?: string;
  condition?: {
    type?: string;
    field?: string;
    value?: string;
    [key: string]: unknown;
  };
  field?: string;
  value?: string | number | boolean;
  actual?: string | number | boolean | null;
  operator?: string;
  formula?: string;
  note?: string;
  child_scores?: number[];
  scores?: number[];
  result?: number;
  score?: number;
  inner_score?: number;
  selector?: string;
  inner_trace?: ScoringSubStep[];
  inner_traces?: Array<ScoringSubStep[] | ScoringSubStep>;
  children?: ScoringSubStep[];
  agg_type?: string;
  evidence_count?: number;
  [key: string]: unknown;
}

export interface PredicateAst {
  type?: string;
  operator?: string;
  [key: string]: unknown;
}

export interface PredicateResult {
  has_aggregation?: boolean;
  predicate_ast?: PredicateAst;
  predicate?: string;
  predicate_score?: number;
  aggregation_labels?: string[];
  scoring_steps?: ScoringSubStep[];
  [key: string]: unknown;
}

export interface ScoredNode {
  tree_path?: string;
  previous_score?: number;
  accumulated_score?: number;
  final_step_score?: number;
  step_score?: number;
  is_selected?: boolean;
  is_filtered_out?: boolean;
  node?: ScoredNodeMeta;
  predicate_results?: PredicateResult[];
  [key: string]: unknown;
}

export interface ScoringTraceStep {
  step_index?: number;
  step_query?: string;
  axis?: "desc" | "child" | string;
  node_test_expr?: NodeTestExpr;
  nodes?: ScoredNode[];
  [key: string]: unknown;
}

export interface PerNodeDetail {
  node?: ScoredNodeMeta;
  score?: number;
  [key: string]: unknown;
}
