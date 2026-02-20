import type { ReactNode } from "react";
import type {
  PredicateResult,
  ScoredNode,
  ScoredNodeMeta,
  ScoringSubStep,
} from "../../types/scoring";

interface ScoreAggregationProps {
  nodeData: ScoredNode;
  onClose: () => void;
}

function scoreColor(score: number): string {
  if (score >= 0.8) return "#22c55e";
  if (score >= 0.5) return "#f59e0b";
  return "#ef4444";
}

function getNodeLabel(node: ScoredNodeMeta | undefined): string {
  if (!node) return "?";
  const attrs = node.attributes || {};
  const type = node.type || "Node";
  if (attrs.name) return String(attrs.name);
  if (attrs.number) return `${type} ${String(attrs.number)}`;
  if (attrs.index) return `${type} ${String(attrs.index)}`;
  return type;
}

function formatPredicateType(predResult: PredicateResult): string {
  if (predResult?.has_aggregation) return "AGGREGATION";
  const ast = predResult.predicate_ast;
  if (!ast) return predResult.predicate || "predicate";
  const type = ast.type || ast.operator || "";
  if (type === "AGG_PREV") return "AGG_PREV";
  if (type === "AGG_EXISTS") return "AGG_EXISTS";
  if (type === "evidence_agg") {
    const op = ast.operator || "agg_max";
    return op.toUpperCase();
  }
  if (type === "atom") return "ATOM";
  if (type === "AND") return "AND";
  if (type === "OR") return "OR";
  if (type === "NOT") return "NOT";
  return type.toUpperCase() || "PREDICATE";
}

function toFixedScore(score: number | undefined): string {
  return (score ?? 0).toFixed(3);
}

function collectAggregationLabels(pred: PredicateResult): string[] {
  if (Array.isArray(pred?.aggregation_labels) && pred.aggregation_labels.length > 0) {
    return pred.aggregation_labels;
  }
  const ast = pred?.predicate_ast;
  if (!ast || typeof ast !== "object") return [];
  const op = String(ast.operator || "");
  if (ast.type === "evidence_agg" || op.startsWith("agg_") || op.startsWith("AGG_")) {
    return [op || "AGG"];
  }
  return [];
}

function normalizeNestedSteps(step: ScoringSubStep): ScoringSubStep[] {
  const normalized: ScoringSubStep[] = [];
  if (Array.isArray(step.inner_trace)) normalized.push(...step.inner_trace);
  if (Array.isArray(step.children)) normalized.push(...step.children);
  if (Array.isArray(step.inner_traces)) {
    for (const traceOrStep of step.inner_traces) {
      if (Array.isArray(traceOrStep)) normalized.push(...traceOrStep);
      else normalized.push(traceOrStep);
    }
  }
  return normalized;
}

function flattenStepLabel(step: ScoringSubStep, nodeLabel: string): string {
  const t = step?.type;
  if (t === "atom") {
    const cond = step.condition;
    if (cond?.field && cond.value) {
      return `${String(cond.field)} =~ "${String(cond.value)}" on ${nodeLabel}`;
    }
    return step.note || `ATOM on ${nodeLabel}`;
  }
  if (t === "id_eq") return `@${step.field} = "${step.value}"`;
  if (t === "or" || t === "and" || t === "avg") {
    const formula = step.formula || t.toUpperCase();
    const size = Array.isArray(step.child_scores) ? step.child_scores.length : 0;
    return `${formula} (${size} children)`;
  }
  if (t === "not") return step.formula || "1 - Score(u, ψ)";
  if (t === "evidence_agg") {
    const agg = String(step.agg_type || "agg").toUpperCase();
    const cnt = step.evidence_count ?? 0;
    const selector = step.selector ? ` on ${step.selector}` : "";
    return `AGG_${agg}${selector} (${cnt} evidence nodes)`;
  }
  return step.formula || step.note || t || "step";
}

function renderScoringSteps(
  steps: ScoringSubStep[],
  nodeLabel: string,
  depth = 0
): ReactNode[] {
  if (!steps || steps.length === 0) return [];
  return steps.map((step, i: number) => {
    const indent = depth * 14;
    const score = step.result ?? step.score;
    const nested = normalizeNestedSteps(step);
    const hasNested = Array.isArray(nested) && nested.length > 0;

    return (
      <div key={`${depth}-${i}`} className="agg-scoring-step" style={{ marginLeft: indent }}>
        <div className="agg-step-main">
          <span className="agg-step-label">{flattenStepLabel(step, nodeLabel)}</span>
          {(score !== undefined || step.inner_score !== undefined) && (
            <span className="agg-step-score" style={{ color: scoreColor(score ?? step.inner_score ?? 0) }}>
              {toFixedScore(score ?? step.inner_score)}
            </span>
          )}
        </div>
        {hasNested && (
          <div className="agg-step-nested">
            {renderScoringSteps(nested, nodeLabel, depth + 1)}
          </div>
        )}
      </div>
    );
  });
}

export default function ScoreAggregation({
  nodeData,
  onClose,
}: ScoreAggregationProps) {
  const predicateResults: PredicateResult[] = nodeData.predicate_results || [];
  const nodeLabel = getNodeLabel(nodeData.node);
  const nodeScore = nodeData.accumulated_score ?? nodeData.final_step_score ?? nodeData.step_score ?? 0;
  const aggregationTags = Array.from(
    new Set(predicateResults.flatMap((pred) => collectAggregationLabels(pred)))
  );

  return (
    <div className="score-aggregation">
      <div className="agg-header">
        <div className="agg-header-left">
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <rect
              x="2"
              y="2"
              width="14"
              height="14"
              rx="3"
              stroke="#8b5cf6"
              strokeWidth="1.5"
            />
            <path
              d="M6 9h6M9 6v6"
              stroke="#8b5cf6"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          </svg>
          <span className="agg-header-title">Score Aggregation</span>
        </div>
        <div className="agg-header-actions">
          <button className="agg-close-btn" onClick={onClose}>
            &times;
          </button>
        </div>
      </div>

      <div className="agg-subtitle">
        Selected node score source and predicate-level breakdown
      </div>

      <div className="agg-selected-node">
        <span className="agg-selected-label">{nodeLabel}</span>
        <span className="agg-selected-score" style={{ color: scoreColor(nodeScore) }}>
          {toFixedScore(nodeScore)}
        </span>
      </div>

      {aggregationTags.length > 0 && (
        <div className="agg-tags-row">
          {aggregationTags.map((tag, idx) => (
            <span key={idx} className="agg-tag">
              {tag}
            </span>
          ))}
        </div>
      )}

      <div className="agg-body">
        {predicateResults.length === 0 && (
          <div className="agg-empty">
            No semantic predicate was applied on this node in the current step.
          </div>
        )}
        {predicateResults.map((pred, idx: number) => {
          const predType = formatPredicateType(pred);
          const predScore = pred.predicate_score ?? 0;
          const predAggTags = collectAggregationLabels(pred);

          return (
            <div key={idx} className="agg-predicate-section">
              <div className="agg-predicate-header">
                <span className="agg-predicate-type">{predType}</span>
                <span
                  className="agg-predicate-score"
                  style={{ color: scoreColor(predScore) }}
                >
                  {predScore.toFixed(3)}
                </span>
              </div>

              {predAggTags.length > 0 && (
                <div className="agg-tags-row">
                  {predAggTags.map((tag, tagIdx) => (
                    <span key={tagIdx} className="agg-tag">
                      {tag}
                    </span>
                  ))}
                </div>
              )}

              {pred.predicate && (
                <div className="agg-formula">
                  {pred.predicate}
                </div>
              )}

              {pred.scoring_steps && pred.scoring_steps.length > 0 && (
                <div className="agg-scoring-steps">
                  {renderScoringSteps(pred.scoring_steps, nodeLabel)}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
