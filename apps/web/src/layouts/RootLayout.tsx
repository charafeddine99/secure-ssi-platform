import React from "react";
import { Outlet, Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { NetworkIndicator } from "../components/common/NetworkIndicator";
import { TrustBadge } from "../components/common/TrustBadge";
import { Shield, BookOpen, Layers, Users, KeyRound, Building2, CheckCircle2, UserCheck } from "lucide-react";

export const RootLayout: React.FC = () => {
  const { user, isDemoEvaluationMode, switchDemoRole } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const handleRoleChange = (role: "HOLDER" | "ISSUER" | "VERIFIER" | "GUARDIAN" | "ADMIN") => {
    switchDemoRole(role);
    if (role === "HOLDER") navigate("/wallet");
    else if (role === "ISSUER") navigate("/issuer");
    else if (role === "VERIFIER") navigate("/verifier");
    else if (role === "GUARDIAN") navigate("/guardian");
    else if (role === "ADMIN") navigate("/admin");
  };

  const isPublicRoute = location.pathname === "/" || location.pathname === "/ecosystem" || location.pathname === "/docs";

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", backgroundColor: "#0b0f19", color: "#f8fafc" }}>
      {/* 1. ACADEMIC PROTOTYPE NOTICE BANNER */}
      <div
        style={{
          backgroundColor: "#1e293b",
          borderBottom: "1px solid rgba(255,255,255,0.08)",
          padding: "5px 16px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          fontSize: "0.72rem",
          color: "#94a3b8"
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ color: "#fbbf24", fontWeight: 700 }}>🔬 ACADEMIC SSI PROTOTYPE:</span>
          <span>Standards-aligned reference implementation (W3C VC 2.0 / OID4VCI / EUDI ARF inspired) — Not an officially certified production service.</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <NetworkIndicator />
        </div>
      </div>

      {/* 2. MAIN APP NAVIGATION BAR */}
      <header
        style={{
          height: "64px",
          backgroundColor: "#111827",
          borderBottom: "1px solid #1f2937",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 20px",
          position: "sticky",
          top: 0,
          zIndex: 40
        }}
      >
        {/* Brand */}
        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          <Link
            to="/"
            style={{
              display: "flex",
              alignItems: "center",
              gap: "10px",
              textDecoration: "none",
              color: "inherit"
            }}
          >
            <div
              style={{
                width: "36px",
                height: "36px",
                borderRadius: "10px",
                backgroundColor: "#2563eb",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#ffffff",
                fontWeight: 800,
                fontSize: "1rem",
                boxShadow: "0 0 12px rgba(37,99,235,0.5)"
              }}
            >
              SSI
            </div>
            <div>
              <div style={{ fontSize: "1rem", fontWeight: 800, letterSpacing: "-0.02em", color: "#f8fafc", lineHeight: 1.1 }}>
                SECURE SSI PLATFORM
              </div>
              <div style={{ fontSize: "0.68rem", color: "#94a3b8", display: "flex", gap: "6px", alignItems: "center", marginTop: "2px" }}>
                <span>Self-Sovereign Identity Architecture</span>
                <TrustBadge level="STANDARDS_ALIGNED" size="sm" />
              </div>
            </div>
          </Link>

          {/* Public Nav Links */}
          <nav style={{ display: "flex", gap: "4px", marginLeft: "20px" }}>
            <Link
              to="/"
              style={{
                padding: "6px 12px",
                borderRadius: "8px",
                fontSize: "0.82rem",
                fontWeight: 600,
                color: location.pathname === "/" ? "#ffffff" : "#94a3b8",
                backgroundColor: location.pathname === "/" ? "rgba(255,255,255,0.06)" : "transparent",
                textDecoration: "none"
              }}
            >
              Overview
            </Link>
            <Link
              to="/ecosystem"
              style={{
                padding: "6px 12px",
                borderRadius: "8px",
                fontSize: "0.82rem",
                fontWeight: 600,
                color: location.pathname === "/ecosystem" ? "#ffffff" : "#94a3b8",
                backgroundColor: location.pathname === "/ecosystem" ? "rgba(255,255,255,0.06)" : "transparent",
                textDecoration: "none"
              }}
            >
              Ecosystem
            </Link>
            <Link
              to="/docs"
              style={{
                padding: "6px 12px",
                borderRadius: "8px",
                fontSize: "0.82rem",
                fontWeight: 600,
                color: location.pathname === "/docs" ? "#ffffff" : "#94a3b8",
                backgroundColor: location.pathname === "/docs" ? "rgba(255,255,255,0.06)" : "transparent",
                textDecoration: "none"
              }}
            >
              Architecture & APIs
            </Link>
          </nav>
        </div>

        {/* 3. EVALUATION ROLE SWITCHER (CLEARLY MARKED FOR DEMO/THESIS) */}
        {isDemoEvaluationMode && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              backgroundColor: "#070a12",
              padding: "4px 8px",
              borderRadius: "10px",
              border: "1px solid #1f2937"
            }}
          >
            <span
              style={{
                fontSize: "0.68rem",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                color: "#94a3b8",
                marginRight: "4px",
                fontWeight: 700
              }}
            >
              DEMO ROLE:
            </span>

            <button
              onClick={() => handleRoleChange("HOLDER")}
              style={{
                padding: "4px 10px",
                borderRadius: "6px",
                fontSize: "0.75rem",
                fontWeight: 600,
                border: "none",
                cursor: "pointer",
                backgroundColor: user?.role === "HOLDER" && !isPublicRoute ? "#2563eb" : "transparent",
                color: user?.role === "HOLDER" && !isPublicRoute ? "#ffffff" : "#94a3b8"
              }}
            >
              🪪 Holder
            </button>

            <button
              onClick={() => handleRoleChange("ISSUER")}
              style={{
                padding: "4px 10px",
                borderRadius: "6px",
                fontSize: "0.75rem",
                fontWeight: 600,
                border: "none",
                cursor: "pointer",
                backgroundColor: user?.role === "ISSUER" && !isPublicRoute ? "#2563eb" : "transparent",
                color: user?.role === "ISSUER" && !isPublicRoute ? "#ffffff" : "#94a3b8"
              }}
            >
              🏛️ Issuer
            </button>

            <button
              onClick={() => handleRoleChange("VERIFIER")}
              style={{
                padding: "4px 10px",
                borderRadius: "6px",
                fontSize: "0.75rem",
                fontWeight: 600,
                border: "none",
                cursor: "pointer",
                backgroundColor: user?.role === "VERIFIER" && !isPublicRoute ? "#2563eb" : "transparent",
                color: user?.role === "VERIFIER" && !isPublicRoute ? "#ffffff" : "#94a3b8"
              }}
            >
              🔍 Verifier
            </button>

            <button
              onClick={() => handleRoleChange("GUARDIAN")}
              style={{
                padding: "4px 10px",
                borderRadius: "6px",
                fontSize: "0.75rem",
                fontWeight: 600,
                border: "none",
                cursor: "pointer",
                backgroundColor: user?.role === "GUARDIAN" && !isPublicRoute ? "#2563eb" : "transparent",
                color: user?.role === "GUARDIAN" && !isPublicRoute ? "#ffffff" : "#94a3b8"
              }}
            >
              🛡️ Guardian
            </button>

            <button
              onClick={() => handleRoleChange("ADMIN")}
              style={{
                padding: "4px 10px",
                borderRadius: "6px",
                fontSize: "0.75rem",
                fontWeight: 600,
                border: "none",
                cursor: "pointer",
                backgroundColor: user?.role === "ADMIN" && !isPublicRoute ? "#2563eb" : "transparent",
                color: user?.role === "ADMIN" && !isPublicRoute ? "#ffffff" : "#94a3b8"
              }}
            >
              ⚙️ Admin
            </button>
          </div>
        )}
      </header>

      {/* Main Outlet */}
      <main style={{ flex: 1, display: "flex", flexDirection: "column" }}>
        <Outlet />
      </main>
    </div>
  );
};
