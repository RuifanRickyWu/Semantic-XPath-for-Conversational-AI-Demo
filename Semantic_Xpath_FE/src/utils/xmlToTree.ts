import type { Node, Edge } from "@xyflow/react";
import dagre from "dagre";

/* ── Types ─────────────────────────────────────────── */

export interface PlanNodeData {
  label: string;
  tagName: string;
  /** Direct text content (for leaf nodes like Item, Title, Summary) */
  textContent?: string;
  /** Un-truncated text for nodes whose label was shortened */
  fullText?: string;
  /** All XML attributes as key-value pairs */
  attributes?: Record<string, string>;
  /** Number of direct child elements */
  childCount: number;
  /** Human-readable path from root, e.g. "Plan > Day 2 > Morning > Item" */
  xpath: string;
  /**
   * Structural path using tag[siblingIndex] notation, matching the backend
   * tree_path format. e.g. "Plan/Day[2]/Morning[1]/Item[1]"
   */
  structuralPath: string;
  /** Backend-style display path used in scoring trace matching. */
  backendPath?: string;
  /** CRUD highlight mode applied via PlanTreeView */
  highlightMode?: "read" | "create" | "update" | "delete" | null;
  /** Whether this node is a direct target (true) or an ancestor along the path (false) */
  isHighlightTarget?: boolean;
  [key: string]: unknown;
}

/* ── Constants ─────────────────────────────────────── */

const NODE_WIDTH = 280;
/** Full rendered height: 14px pill + 56px card + 7px bottom handle */
const NODE_HEIGHT = 80;

const RANK_SEP = 100;
const NODE_SEP = 50;
type LayoutDirection = "LR" | "TB";

/* ── Label helpers ─────────────────────────────────── */

function truncate(text: string, max: number): string {
  const trimmed = text.trim();
  return trimmed.length > max ? trimmed.slice(0, max) + "..." : trimmed;
}

/**
 * Derive a human-friendly label for an XML element.
 */
function labelForElement(el: Element): string {
  const tag = el.tagName;
  const nameAttr = el.getAttribute("name");
  const indexAttr = el.getAttribute("index") ?? el.getAttribute("number");

  switch (tag) {
    case "Plan":
      return "Root";
    case "Meta":
      return "Meta";
    case "Title":
    case "Summary":
      return truncate(el.textContent ?? tag, 35);
    case "Day": {
      const num = indexAttr ?? "?";
      return `Day ${num}`;
    }
    case "Morning":
    case "Afternoon":
    case "Evening":
    case "Notes":
    case "Logistics":
      return tag;
    case "Item":
      return truncate(el.textContent ?? "Item", 35);
    default:
      if (nameAttr) return truncate(nameAttr, 35);
      return tag;
  }
}

/**
 * Mirror backend NodeUtils.get_name() behavior for stable path matching.
 */
function backendNameForElement(el: Element): string {
  const index = el.getAttribute("index") ?? el.getAttribute("number");
  if (index !== null) return `${el.tagName} ${index}`;

  const nameAttr = el.getAttribute("name");
  if (nameAttr) return nameAttr;

  for (const field of ["name", "title", "label"]) {
    const child = el.querySelector(`:scope > ${field}`);
    const text = child?.textContent?.trim();
    if (text) return text;
  }

  return el.tagName;
}

/**
 * Derive the pill / tag text shown above the card.
 */
function tagForElement(el: Element): string {
  const tag = el.tagName;

  switch (tag) {
    case "Plan":
      return "Root";
    case "Day":
      return "Day";
    case "Item":
      return "Item";
    default:
      return tag;
  }
}

/**
 * Compute the 1-based sibling index among same-tag siblings.
 */
function siblingIndex(el: Element): number {
  const parent = el.parentElement;
  if (!parent) return 1;
  const sameTag = Array.from(parent.children).filter(
    (c) => c.tagName === el.tagName
  );
  return sameTag.indexOf(el) + 1;
}

/* ── Recursive tree walk ───────────────────────────── */

function walkElement(
  el: Element,
  parentId: string | null,
  parentDisplayPath: string,
  parentBackendPath: string,
  parentStructuralPath: string,
  nodes: Node<PlanNodeData>[],
  edges: Edge[],
  idCounter: { value: number }
): void {
  const id = `node-${idCounter.value++}`;
  const label = labelForElement(el);
  const xpath = parentDisplayPath
    ? `${parentDisplayPath} > ${label}`
    : label;
  const backendName = backendNameForElement(el);
  const backendPath = parentBackendPath
    ? `${parentBackendPath} > ${backendName}`
    : backendName;

  // Build structural path: "Plan/Day[2]/Morning[1]/Item[1]"
  const idx = siblingIndex(el);
  const segment = `${el.tagName}[${idx}]`;
  const structuralPath = parentStructuralPath
    ? `${parentStructuralPath}/${segment}`
    : segment;

  const directText = Array.from(el.childNodes)
    .filter((n) => n.nodeType === Node.TEXT_NODE)
    .map((n) => n.textContent?.trim() ?? "")
    .join(" ")
    .trim();

  // Collect all XML attributes
  const attrs: Record<string, string> = {};
  for (let i = 0; i < el.attributes.length; i++) {
    const a = el.attributes[i];
    attrs[a.name] = a.value;
  }

  const children = Array.from(el.children);

  const nodeData: PlanNodeData = {
    label,
    tagName: tagForElement(el),
    textContent: directText || undefined,
    fullText: directText || undefined,
    attributes: Object.keys(attrs).length > 0 ? attrs : undefined,
    childCount: children.length,
    xpath,
    backendPath,
    structuralPath,
  };

  nodes.push({
    id,
    type: "planNode",
    data: nodeData,
    position: { x: 0, y: 0 }, // will be set by dagre
  });

  if (parentId) {
    edges.push({
      id: `edge-${parentId}-${id}`,
      source: parentId,
      target: id,
      type: "smoothstep",
    });
  }

  // Recurse into child elements
  for (const child of children) {
    walkElement(
      child,
      id,
      xpath,
      backendPath,
      structuralPath,
      nodes,
      edges,
      idCounter
    );
  }
}

/* ── Layout with dagre ─────────────────────────────── */

function applyDagreLayout(
  nodes: Node<PlanNodeData>[],
  edges: Edge[],
  direction: LayoutDirection
): void {
  const g = new dagre.graphlib.Graph();
  g.setGraph({
    rankdir: direction,
    ranksep: RANK_SEP,
    nodesep: NODE_SEP,
    marginx: 20,
    marginy: 20,
  });
  g.setDefaultEdgeLabel(() => ({}));

  for (const node of nodes) {
    g.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  }

  for (const edge of edges) {
    g.setEdge(edge.source, edge.target);
  }

  dagre.layout(g);

  for (const node of nodes) {
    const pos = g.node(node.id);
    // dagre returns center positions; React Flow uses top-left
    node.position = {
      x: pos.x - NODE_WIDTH / 2,
      y: pos.y - NODE_HEIGHT / 2,
    };
  }
}

/* ── Public API ────────────────────────────────────── */

export function parseXmlToTree(
  xmlString: string,
  options?: { direction?: LayoutDirection }
): {
  nodes: Node<PlanNodeData>[];
  edges: Edge[];
} {
  const parser = new DOMParser();
  const doc = parser.parseFromString(xmlString, "application/xml");

  const parseError = doc.querySelector("parsererror");
  if (parseError) {
    console.error("XML parse error:", parseError.textContent);
    return { nodes: [], edges: [] };
  }

  const root = doc.documentElement;
  const nodes: Node<PlanNodeData>[] = [];
  const edges: Edge[] = [];
  const idCounter = { value: 0 };

  walkElement(root, null, "", "", "", nodes, edges, idCounter);
  applyDagreLayout(nodes, edges, options?.direction ?? "LR");

  return { nodes, edges };
}
