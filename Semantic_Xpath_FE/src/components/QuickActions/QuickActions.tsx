import "./QuickActions.css";

interface QuickAction {
  label: string;
  icon: React.ReactNode;
  query: string;
}

interface QuickActionsProps {
  onSelect: (query: string) => void;
}

const actions: QuickAction[] = [
  {
    label: "Itinerary",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <path
          d="M10 2a6 6 0 0 1 6 6c0 4.5-6 10-6 10S4 12.5 4 8a6 6 0 0 1 6-6z"
          stroke="#7c3aed"
          strokeWidth="1.5"
        />
        <circle cx="10" cy="8" r="2" stroke="#7c3aed" strokeWidth="1.5" />
      </svg>
    ),
    query: "5 days travel plan in Toronto",
  },
  {
    label: "Todo List",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <rect x="3" y="3" width="14" height="14" rx="2" stroke="#7c3aed" strokeWidth="1.5" />
        <path d="M7 10l2 2 4-4" stroke="#7c3aed" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
    query: "I'm a CS undergrad planning for grad school application, give me a weekly todo list",
  },
  {
    label: "Nutrition",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <path
          d="M10 2c-3 0-5 2-5 5 0 4 5 11 5 11s5-7 5-11c0-3-2-5-5-5z"
          stroke="#7c3aed"
          strokeWidth="1.5"
        />
        <path d="M8 7h4m-2-2v4" stroke="#7c3aed" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    ),
    query: "Create a 7-day nutrition plan for muscle building",
  },
];

export default function QuickActions({ onSelect }: QuickActionsProps) {
  return (
    <div className="quick-actions">
      {actions.map((action) => (
        <button
          key={action.label}
          className="quick-action-chip"
          onClick={() => onSelect(action.query)}
        >
          {action.icon}
          <span>{action.label}</span>
        </button>
      ))}
    </div>
  );
}
