import "./Header.css";

export default function Header() {
  return (
    <header className="header">
      <div className="header-left">
        <div className="header-logo">
          <svg
            width="26"
            height="28"
            viewBox="0 0 26 28"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M13 0L26 7V21L13 28L0 21V7L13 0Z"
              fill="url(#logo-gradient)"
            />
            <path
              d="M13 4L22 9V19L13 24L4 19V9L13 4Z"
              fill="white"
              fillOpacity="0.3"
            />
            <defs>
              <linearGradient
                id="logo-gradient"
                x1="0"
                y1="0"
                x2="26"
                y2="28"
              >
                <stop stopColor="#7C3AED" />
                <stop offset="1" stopColor="#A78BFA" />
              </linearGradient>
            </defs>
          </svg>
        </div>
        <span className="header-title">Semantic Xpath</span>
      </div>
      <div className="header-right">
        <button className="header-icon-btn" aria-label="Logs">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <rect
              x="3"
              y="3"
              width="14"
              height="14"
              rx="2"
              stroke="#666"
              strokeWidth="1.5"
            />
            <line
              x1="6"
              y1="7"
              x2="14"
              y2="7"
              stroke="#666"
              strokeWidth="1.5"
            />
            <line
              x1="6"
              y1="10"
              x2="14"
              y2="10"
              stroke="#666"
              strokeWidth="1.5"
            />
            <line
              x1="6"
              y1="13"
              x2="11"
              y2="13"
              stroke="#666"
              strokeWidth="1.5"
            />
          </svg>
        </button>
        <button className="header-icon-btn" aria-label="Settings">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <circle cx="10" cy="10" r="2" stroke="#666" strokeWidth="1.5" />
            <path
              d="M10 2v2m0 12v2m-8-8h2m12 0h2m-2.93-5.07-1.41 1.41m-7.32 7.32-1.41 1.41m0-10.14 1.41 1.41m7.32 7.32 1.41 1.41"
              stroke="#666"
              strokeWidth="1.5"
            />
          </svg>
        </button>
        <div className="header-avatar">
          <div className="avatar-circle" />
        </div>
        <span className="header-username">Sally</span>
      </div>
    </header>
  );
}
