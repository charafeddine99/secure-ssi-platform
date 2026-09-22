import React from "react";
import { Link } from "react-router-dom";
import { AlertCircle, ArrowLeft } from "lucide-react";

export const NotFoundPage: React.FC = () => {
  return (
    <div
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "60px 24px",
        textAlign: "center"
      }}
    >
      <div
        style={{
          width: "64px",
          height: "64px",
          borderRadius: "50%",
          backgroundColor: "rgba(239, 68, 68, 0.1)",
          border: "1px solid rgba(239, 68, 68, 0.3)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#f87171",
          marginBottom: "20px"
        }}
      >
        <AlertCircle size={32} />
      </div>

      <h1 style={{ fontSize: "2.4rem", fontWeight: 800, color: "#ffffff", margin: "0 0 8px 0" }}>
        404 — Page Not Found
      </h1>
      <p style={{ fontSize: "1rem", color: "#94a3b8", maxWidth: "460px", margin: "0 0 24px 0" }}>
        The requested SSI route does not exist. Return to the public home or select a role portal from the top bar.
      </p>

      <Link
        to="/"
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "8px",
          padding: "10px 20px",
          borderRadius: "8px",
          backgroundColor: "#2563eb",
          color: "#ffffff",
          fontWeight: 600,
          textDecoration: "none",
          fontSize: "0.9rem"
        }}
      >
        <ArrowLeft size={16} />
        Back to Overview
      </Link>
    </div>
  );
};
