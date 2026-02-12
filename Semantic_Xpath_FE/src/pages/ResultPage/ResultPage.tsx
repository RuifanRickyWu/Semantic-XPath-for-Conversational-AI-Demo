import { useLocation, useNavigate } from "react-router-dom";
import type { ColdStartResponse } from "../../types/coldStart";
import "./ResultPage.css";

interface LocationState {
  result: ColdStartResponse;
  query: string;
}

export default function ResultPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const state = location.state as LocationState | null;

  if (!state?.result) {
    return (
      <div className="result-page">
        <div className="result-empty">
          <p>No result data found. Please start from the home page.</p>
          <button className="result-back-btn" onClick={() => navigate("/")}>
            Back to Home
          </button>
        </div>
      </div>
    );
  }

  const { result, query } = state;
  const display = result.display;

  return (
    <div className="result-page">
      <div className="result-container">
        <button className="result-back-btn" onClick={() => navigate("/")}>
          &larr; New Query
        </button>

        <div className="result-query-section">
          <h2 className="result-section-title">Query</h2>
          <p className="result-query-text">{query}</p>
        </div>

        {result.user_facing && (
          <div className="result-section">
            <h2 className="result-section-title">Plan</h2>
            <pre className="result-content">{result.user_facing}</pre>
          </div>
        )}

        {display?.summary && (
          <div className="result-section">
            <h2 className="result-section-title">Summary</h2>
            <pre className="result-content">{display.summary}</pre>
          </div>
        )}

        {display?.task_schema && (
          <div className="result-section">
            <h2 className="result-section-title">Task Schema</h2>
            <pre className="result-content code">{display.task_schema}</pre>
          </div>
        )}

        {display?.domain_schema && (
          <div className="result-section">
            <h2 className="result-section-title">Domain Schema</h2>
            <pre className="result-content code">{display.domain_schema}</pre>
          </div>
        )}

        {display?.memory_xml && (
          <div className="result-section">
            <h2 className="result-section-title">Memory XML</h2>
            <pre className="result-content code">{display.memory_xml}</pre>
          </div>
        )}

        {result.warnings && result.warnings.length > 0 && (
          <div className="result-section">
            <h2 className="result-section-title">Warnings</h2>
            <ul className="result-warnings">
              {result.warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
