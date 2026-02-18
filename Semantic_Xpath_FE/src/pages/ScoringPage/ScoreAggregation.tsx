interface ScoreAggregationProps {
  nodeData: any;
  onClose: () => void;
}

function scoreColor(score: number): string {
  if (score >= 0.7) return "#22c55e";
  if (score >= 0.4) return "#f59e0b";
  return "#ef4444";
}

function getNodeLabel(node: any): string {
  if (!node) return "?";
  const attrs = node.attributes || {};
  const type = node.type || "Node";
  if (attrs.name) return attrs.name;
  if (attrs.number) return `${type} ${attrs.number}`;
  return type;
}

function formatPredicateType(predResult: any): string {
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

function renderScoringSteps(steps: any[], depth = 0) {
  if (!steps || steps.length === 0) return [];

  return steps.map((step: any, i: number) => {
    const indent = depth * 16;

    if (step.type === "leaf_score" || step.type === "atom_score") {
      return (
        <div
          key={i}
          className="agg-scoring-step"
          style={{ marginLeft: indent }}
        >
          <span className="agg-step-label">
            {step.field || "content"} =~ "{step.value || ""}"
          </span>
          <span
            className="agg-step-score"
            style={{ color: scoreColor(step.score ?? 0) }}
          >
            {(step.score ?? 0).toFixed(3)}
          </span>
        </div>
      );
    }

    if (step.type === "evidence_node") {
      return (
        <div
          key={i}
          className="agg-evidence-node"
          style={{ marginLeft: indent }}
        >
          <span className="agg-evidence-label">
            {getNodeLabel(step.node)}
          </span>
          <span
            className="agg-evidence-score"
            style={{ color: scoreColor(step.score ?? 0) }}
          >
            {(step.score ?? 0).toFixed(3)}
          </span>
          {step.children &&
            renderScoringSteps(step.children, depth + 1)}
        </div>
      );
    }

    if (step.type === "aggregation") {
      return (
        <div key={i} className="agg-step-group" style={{ marginLeft: indent }}>
          <div className="agg-step-header">
            {step.operator || "agg"}({step.count ?? "?"} children)
          </div>
          {step.child_scores &&
            step.child_scores.map((cs: any, j: number) => (
              <div key={j} className="agg-child-score-row">
                <span className="agg-child-label">
                  {getNodeLabel(cs.node)}
                </span>
                <span
                  className="agg-child-score"
                  style={{ color: scoreColor(cs.score ?? 0) }}
                >
                  {(cs.score ?? 0).toFixed(3)}
                </span>
              </div>
            ))}
          <div className="agg-step-result">
            <span className="agg-result-formula">
              {step.operator || "agg"}({step.count ?? "?"} children)
            </span>
            <span className="agg-result-equals">=</span>
            <span
              className="agg-result-score"
              style={{ color: scoreColor(step.result ?? 0) }}
            >
              {(step.result ?? 0).toFixed(3)}
            </span>
          </div>
        </div>
      );
    }

    // Generic fallback
    return (
      <div key={i} className="agg-scoring-step" style={{ marginLeft: indent }}>
        <span className="agg-step-label">{step.description || JSON.stringify(step).slice(0, 60)}</span>
        {step.score !== undefined && (
          <span
            className="agg-step-score"
            style={{ color: scoreColor(step.score ?? 0) }}
          >
            {(step.score ?? 0).toFixed(3)}
          </span>
        )}
      </div>
    );
  });
}

export default function ScoreAggregation({
  nodeData,
  onClose,
}: ScoreAggregationProps) {
  const predicateResults: any[] = nodeData.predicate_results || [];
  const nodeLabel = getNodeLabel(nodeData.node);
  const children: any[] = nodeData.children || [];

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
        click node to display score aggregation/propagation
      </div>

      <div className="agg-body">
        {predicateResults.map((pred: any, idx: number) => {
          const predType = formatPredicateType(pred);
          const predScore = pred.predicate_score ?? 0;

          return (
            <div key={idx} className="agg-predicate-section">
              <div className="agg-predicate-header">
                <span className="agg-predicate-chevron">&or;</span>
                <span className="agg-predicate-type">{predType}</span>
                <span className="agg-predicate-node">{nodeLabel}</span>
                <span
                  className="agg-predicate-score"
                  style={{ color: scoreColor(predScore) }}
                >
                  {predScore.toFixed(3)}
                </span>
              </div>

              {pred.predicate && (
                <div className="agg-formula">
                  * {pred.predicate}
                </div>
              )}

              {pred.scoring_steps && pred.scoring_steps.length > 0 && (
                <div className="agg-scoring-steps">
                  {renderScoringSteps(pred.scoring_steps)}
                </div>
              )}

              {/* Render child evidence nodes if this is an aggregation predicate */}
              {children.length > 0 &&
                (predType.includes("AGG") || predType.includes("agg")) && (
                  <div className="agg-children-section">
                    {children.slice(0, 10).map((child: any, cIdx: number) => (
                      <div key={cIdx} className="agg-child-row">
                        <span className="agg-child-label">
                          {getNodeLabel(child)}
                        </span>
                        <span
                          className="agg-child-score"
                          style={{
                            color: scoreColor(child.score ?? child.accumulated_score ?? 0),
                          }}
                        >
                          {(child.score ?? child.accumulated_score ?? 0).toFixed(3)}
                        </span>
                      </div>
                    ))}
                    {children.length > 10 && (
                      <div className="agg-child-more">
                        +{children.length - 10} more
                      </div>
                    )}
                  </div>
                )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
