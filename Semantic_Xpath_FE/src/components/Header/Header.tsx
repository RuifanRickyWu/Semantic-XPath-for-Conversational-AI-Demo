import { useAppState } from "../../context/useAppState";
import { useNavigate } from "react-router-dom";
import "./Header.css";

export default function Header() {
  const { headerSlot } = useAppState();
  const navigate = useNavigate();

  const handleHomeClick = () => {
    navigate("/");
  };

  return (
    <div className="header-wrapper">
      <header className="header">
        <div className="header-left">
          <button type="button" className="header-home-btn" onClick={handleHomeClick}>
            <div className="header-logo">
              <svg
                width="27"
                height="28"
                viewBox="0 0 27 28"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M11.9648 0.294773C12.3198 0.101423 12.7188 0 13.1244 0C13.5301 0 13.929 0.101423 14.284 0.294773L25.0116 6.13544C25.3867 6.33941 25.6994 6.63873 25.9172 7.00225C26.1351 7.36576 26.25 7.78015 26.25 8.20228V19.7975C26.2497 20.2194 26.1347 20.6335 25.9169 20.9968C25.6991 21.3601 25.3865 21.6593 25.0116 21.8632L14.284 27.7055C13.9292 27.8987 13.5304 28 13.125 28C12.7196 28 12.3208 27.8987 11.966 27.7055L1.23841 21.8643C0.863347 21.6603 0.550637 21.361 0.332835 20.9975C0.115033 20.634 9.98483e-05 20.2196 0 19.7975V8.20285C0.000408116 7.78102 0.115487 7.367 0.333273 7.00383C0.551059 6.64065 0.863603 6.34158 1.23841 6.1377L11.9642 0.294206V0.294773H11.9648ZM4.62349 9.3703C4.54711 9.50595 4.49862 9.65511 4.48079 9.80924C4.46296 9.96337 4.47614 10.1195 4.51957 10.2686C4.563 10.4177 4.63583 10.5569 4.7339 10.6782C4.83198 10.7996 4.95337 10.9007 5.09113 10.9758L11.9269 14.6969V22.1176C11.9269 22.4307 12.0531 22.731 12.2778 22.9524C12.5025 23.1738 12.8072 23.2981 13.125 23.2981C13.4428 23.2981 13.7475 23.1738 13.9722 22.9524C14.1969 22.731 14.3232 22.4307 14.3232 22.1176V14.6969L21.1589 10.9736C21.4254 10.8164 21.6195 10.5634 21.7004 10.2679C21.7812 9.97237 21.7424 9.6575 21.5921 9.38965C21.4419 9.12179 21.1919 8.9219 20.895 8.83213C20.598 8.74235 20.2773 8.7697 20.0004 8.90842L13.125 12.6511L6.25132 8.90842C5.9732 8.75712 5.64548 8.72084 5.34022 8.80756C5.03496 8.89428 4.77715 9.0969 4.62349 9.37087V9.3703Z"
                  fill="#8561D6"
                />
              </svg>
            </div>
            <span className="header-title">SemanticXpath Chat</span>
          </button>
        </div>
        {headerSlot && <div className="header-center">{headerSlot}</div>}
        <div className="header-right">
          <div className="header-avatar">
            <img className="avatar-circle" src="/assets/actual-user.png" alt="User avatar" />
          </div>
          <span className="header-username">User</span>
        </div>
      </header>
    </div>
  );
}
