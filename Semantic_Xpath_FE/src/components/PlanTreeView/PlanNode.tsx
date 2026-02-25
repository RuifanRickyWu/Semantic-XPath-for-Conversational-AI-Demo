import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { PlanNodeData } from "../../utils/xmlToTree";

function PlanNodeComponent({ data }: NodeProps) {
  const {
    label,
    tagName,
    fullText,
    attributes,
    childCount,
    xpath,
    highlightMode,
    isHighlightTarget,
  } = data as PlanNodeData;

  // Build CSS class list for the card based on highlight state
  const cardClasses = ["plan-node-card"];
  if (highlightMode) {
    if (isHighlightTarget) {
      cardClasses.push(`plan-node-highlight-${highlightMode}`);
    } else {
      cardClasses.push(`plan-node-highlight-${highlightMode}-path`);
    }
  }

  // Build CSS class list for the pill
  const pillClasses = ["plan-node-pill"];
  if (highlightMode) {
    pillClasses.push(`plan-node-pill-${highlightMode}`);
  }

  return (
    <div className="plan-node-wrapper">
      {/* Target handle (top) */}
      <Handle
        type="target"
        position={Position.Top}
        className="plan-node-handle"
      />

      {/* Pill tag above the card */}
      <div className={pillClasses.join(" ")}>{tagName}</div>

      {/* Card body — hover zone for the tooltip */}
      <div className={cardClasses.join(" ")}>
        <span className="plan-node-label">{label}</span>
        <button className="plan-node-menu" aria-label="Options" tabIndex={-1}>
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <circle cx="10" cy="5" r="1.5" fill="#9ca3af" />
            <circle cx="10" cy="10" r="1.5" fill="#9ca3af" />
            <circle cx="10" cy="15" r="1.5" fill="#9ca3af" />
          </svg>
        </button>

        {/* Tooltip — always in DOM, shown/hidden via CSS :hover */}
        <div className="plan-node-tooltip">
          <div className="plan-node-tooltip-row">
            <span className="plan-node-tooltip-label">Type</span>
            <span className="plan-node-tooltip-value">{tagName}</span>
          </div>

          {fullText && (
            <div className="plan-node-tooltip-row">
              <span className="plan-node-tooltip-label">Text</span>
              <span className="plan-node-tooltip-value">{fullText}</span>
            </div>
          )}

          {attributes &&
            Object.entries(attributes).map(([key, value]) => (
              <div className="plan-node-tooltip-row" key={key}>
                <span className="plan-node-tooltip-label">{key}</span>
                <span className="plan-node-tooltip-value">{value}</span>
              </div>
            ))}

          <div className="plan-node-tooltip-row">
            <span className="plan-node-tooltip-label">Path</span>
            <span className="plan-node-tooltip-value plan-node-tooltip-path">
              {xpath}
            </span>
          </div>

          {childCount > 0 && (
            <div className="plan-node-tooltip-row">
              <span className="plan-node-tooltip-label">Children</span>
              <span className="plan-node-tooltip-value">{childCount}</span>
            </div>
          )}
        </div>
      </div>

      {/* Source handle (bottom) */}
      <Handle
        type="source"
        position={Position.Bottom}
        className="plan-node-handle"
      />
    </div>
  );
}

export default memo(PlanNodeComponent);
