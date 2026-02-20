import "./QuickActions.css";

interface QuickAction {
  label: string;
  icon: string;
  query: string;
}

interface QuickActionsProps {
  onSelect: (query: string) => void;
}

const actions: QuickAction[] = [
  {
    label: "Itinerary",
    icon: "/assets/itin_icon.svg",
    query: "3 days business trip plan in San Diego",
  },
  {
    label: "Todo List",
    icon: "/assets/todo_icon.svg",
    query: "I'm a CS undergrad planning for grad school application, give me a weekly todo list",
  },
  {
    label: "Nutrition",
    icon: "/assets/nutrition_icon.svg",
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
          <img src={action.icon} alt={action.label} className="quick-action-icon" />
          <span>{action.label}</span>
        </button>
      ))}
    </div>
  );
}
