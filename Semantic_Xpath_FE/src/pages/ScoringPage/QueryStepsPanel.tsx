interface QueryStepsPanelProps {
  scoringTrace: any[];
  perNodeDetail: any[];
  activeStepIndex: number | null;
  onStepClick: (index: number) => void;
}

function getNodeLabel(node: any): string {
  if (!node) return "?";
  const attrs = node.attributes || {};
  const type = node.type || "Node";
  if (attrs.name) return `${type}: ${attrs.name}`;
  if (attrs.number) return `${type} ${attrs.number}`;
  if (attrs.task_id) return `${type}[${attrs.task_id}]`;
  if (attrs.version_id) return `${type}[${attrs.version_id}]`;
  return type;
}

function scoreColor(score: number): string {
  if (score >= 0.7) return "#22c55e";
  if (score >= 0.4) return "#f59e0b";
  return "#ef4444";
}

function formatNodeTestExpr(expr: any): string {
  if (!expr || typeof expr !== "object") return "*";
  const type = expr.type;
  if (type === "leaf") {
    const test = expr.test || {};
    const kind = test.kind;
    let result = kind === "wildcard" ? "*" : test.name || "*";

    if (test.index) {
      const idx = test.index;
      const start = idx.start;
      if (idx.to_end) result += `[${start}:]`;
      else if (idx.end !== undefined) result += `[${start}:${idx.end}]`;
      else result += `[${start}]`;
    }

    if (test.predicate) {
      const predicateText =
        typeof test.predicate_str === "string" && test.predicate_str.length > 0
          ? test.predicate_str
          : "predicate";
      result += `[${predicateText}]`;
    }

    if (test.relative_index) {
      const offset = test.relative_index.offset;
      const sign = offset >= 0 ? "+" : "";
      result += `[@${sign}${offset}]`;
    }

    return result;
  }

  if (type === "and" || type === "or") {
    const children = Array.isArray(expr.children) ? expr.children : [];
    const joiner = type.toUpperCase();
    return children.map(formatNodeTestExpr).join(` ${joiner} `);
  }

  return "*";
}

function formatStepQuery(step: any): string {
  const axis = step.axis === "desc" ? "//" : "";
  const testExpr = formatNodeTestExpr(step.node_test_expr);
  return `${axis}${testExpr}`;
}

function getStepTypeLabel(step: any): string {
  const query = step.step_query || "";
  if (step.step_index === 0 && /root/i.test(query)) return "Root";
  const hasPredicates = (step.nodes || []).some(
    (n: any) => n.predicate_results && n.predicate_results.length > 0
  );
  if (hasPredicates) return "node_test_expr";
  return "node_test_expr";
}

export default function QueryStepsPanel({
  scoringTrace,
  perNodeDetail,
  activeStepIndex,
  onStepClick,
}: QueryStepsPanelProps) {
  return (
    <div className="query-steps-panel">
      <div className="qsp-title">
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
          <path
            d="M9 1.5a7.5 7.5 0 100 15 7.5 7.5 0 000-15zm0 0V9l3.75 3.75"
            stroke="#8b5cf6"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        Query Steps
      </div>

      <div className="qsp-steps-list">
        {scoringTrace.map((step, idx) => {
          const isActive = activeStepIndex === idx;
          const nodes: any[] = step.nodes || [];

          return (
            <div
              key={idx}
              className={`qsp-step-card ${isActive ? "qsp-step-active" : ""}`}
              onClick={() => onStepClick(idx)}
            >
              <div className="qsp-step-header">
                <div className="qsp-step-name">
                  <span className="qsp-step-type-label">
                    {getStepTypeLabel(step)}
                  </span>
                  <span className="qsp-step-badge">
                    Step {String(idx + 1).padStart(2, "0")}
                  </span>
                </div>
              </div>

              <div className="qsp-step-query">{formatStepQuery(step)}</div>

              {isActive && nodes.length > 0 && (
                <div className="qsp-step-results">
                  <div className="qsp-results-header">RESULT NODES</div>
                  {nodes.map((n: any, nIdx: number) => (
                    <div key={nIdx} className="qsp-result-row">
                      <span className="qsp-result-label">
                        {getNodeLabel(n.node)}
                      </span>
                      <span
                        className="qsp-result-score"
                        style={{ color: scoreColor(n.accumulated_score ?? 0) }}
                      >
                        {(n.accumulated_score ?? 0).toFixed(3)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {perNodeDetail.length > 0 && (
        <div className="qsp-final-result">
          <div className="qsp-final-header">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path
                d="M8 1l2.35 4.76 5.25.77-3.8 3.7.9 5.24L8 13.27l-4.7 2.47.9-5.24-3.8-3.7 5.25-.77L8 1z"
                stroke="#8b5cf6"
                strokeWidth="1.2"
                strokeLinejoin="round"
              />
            </svg>
            Final Result
            <span className="qsp-final-topk">Top-k</span>
          </div>
          <div className="qsp-final-count">
            {scoringTrace.length > 0
              ? (scoringTrace[scoringTrace.length - 1].nodes || []).length
              : 0}{" "}
            &rarr; {perNodeDetail.length}
          </div>
          {perNodeDetail.map((detail: any, i: number) => (
            <div key={i} className="qsp-final-row">
              <span className="qsp-final-rank">#{i + 1}</span>
              <span className="qsp-final-label">
                {getNodeLabel(detail.node)}
              </span>
              <span
                className="qsp-final-score"
                style={{ color: scoreColor(detail.score ?? 0) }}
              >
                {(detail.score ?? 0).toFixed(3)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
