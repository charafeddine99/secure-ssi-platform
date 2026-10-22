import React from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { LogOut, UserCheck } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { roleHomePath } from "../routes/roleNavigation";
import { BrandMark } from "../components/common/BrandMark";

export const RootLayout: React.FC = () => {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const isLoginPage = location.pathname === "/login";
  const accountPath = user ? roleHomePath(user.role) : "/login";

  const navItems = [
    { path: "/", label: "Home" },
    { path: "/ecosystem", label: "Directory" },
    { path: "/docs", label: "Architecture" }
  ];

  return (
    <div className="app-shell" style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <header className="app-header" aria-label="Main header">
        <div className="app-header-brand-nav">
          <Link className="app-brand-link" to="/" aria-label="Secure SSI Platform home">
            <span className="app-brand-mark"><BrandMark size={30} /></span>
            <span className="app-brand-name">Secure SSI Platform</span>
          </Link>

          {!isLoginPage && !user && (
            <nav className="app-public-nav" aria-label="Main navigation">
              {navItems.map((item) => (
                <Link
                  key={item.path}
                  aria-current={location.pathname === item.path ? "page" : undefined}
                  to={item.path}
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          )}
        </div>

        {!isLoginPage && (
          <div className="app-account-actions">
            {user ? (
              <>
                <Link
                  aria-current={location.pathname === accountPath ? "page" : undefined}
                  to={accountPath}
                  className="app-account-link"
                >
                  <UserCheck size={16} aria-hidden="true" />
                  <span>My workspace</span>
                </Link>
                <button
                  type="button"
                  className="app-signout-button"
                  onClick={() => {
                    logout();
                    navigate("/login", { replace: true });
                  }}
                >
                  <LogOut size={16} aria-hidden="true" />
                  <span>Sign out</span>
                </button>
              </>
            ) : (
              <Link to="/login" className="app-account-link">
                <UserCheck size={16} aria-hidden="true" />
                <span>Sign in</span>
              </Link>
            )}
          </div>
        )}
      </header>

      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
};
