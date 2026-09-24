import React, { useEffect, useRef, useState } from "react";
import QRCode from "qrcode";
import { Copy, Check, Download, ExternalLink } from "lucide-react";

interface QRCodeDisplayProps {
  value: string;
  size?: number;
  title?: string;
  subtitle?: string;
}

export const QRCodeDisplay: React.FC<QRCodeDisplayProps> = ({
  value,
  size = 220,
  title,
  subtitle,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (canvasRef.current && value) {
      QRCode.toCanvas(
        canvasRef.current,
        value,
        {
          width: size,
          margin: 2,
          color: {
            dark: "#0f172a",
            light: "#ffffff",
          },
        },
        (error) => {
          if (error) {
            console.error("QR Code generation error:", error);
          }
        }
      );
    }
  }, [value, size]);

  const handleCopy = () => {
    navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    if (!canvasRef.current) return;
    const url = canvasRef.current.toDataURL("image/png");
    const a = document.createElement("a");
    a.href = url;
    a.download = `ssi-qr-${Date.now()}.png`;
    a.click();
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        padding: "20px",
        background: "rgba(15, 23, 42, 0.6)",
        border: "1px solid rgba(148, 163, 184, 0.15)",
        borderRadius: "16px",
        backdropFilter: "blur(12px)",
        gap: "14px",
        maxWidth: `${size + 60}px`,
      }}
    >
      {title && (
        <div style={{ textAlign: "center" }}>
          <h4 style={{ margin: "0 0 4px 0", fontSize: "1rem", color: "#f8fafc", fontWeight: 600 }}>
            {title}
          </h4>
          {subtitle && (
            <p style={{ margin: 0, fontSize: "0.75rem", color: "#94a3b8" }}>
              {subtitle}
            </p>
          )}
        </div>
      )}

      {/* QR Canvas Box */}
      <div
        style={{
          background: "#ffffff",
          padding: "10px",
          borderRadius: "12px",
          boxShadow: "0 8px 24px rgba(0, 0, 0, 0.25)",
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
        }}
      >
        <canvas ref={canvasRef} />
      </div>

      {/* Action Buttons */}
      <div style={{ display: "flex", gap: "8px", width: "100%" }}>
        <button
          type="button"
          onClick={handleCopy}
          style={{
            flex: 1,
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "6px",
            padding: "8px 12px",
            fontSize: "0.8rem",
            fontWeight: 500,
            background: copied ? "rgba(16, 185, 129, 0.2)" : "rgba(59, 130, 246, 0.15)",
            color: copied ? "#34d399" : "#60a5fa",
            border: `1px solid ${copied ? "rgba(16, 185, 129, 0.3)" : "rgba(59, 130, 246, 0.3)"}`,
            borderRadius: "8px",
            cursor: "pointer",
            transition: "all 0.2s ease",
          }}
        >
          {copied ? <Check size={14} /> : <Copy size={14} />}
          {copied ? "Copied" : "Copy URI"}
        </button>

        <button
          type="button"
          onClick={handleDownload}
          style={{
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "8px 12px",
            fontSize: "0.8rem",
            background: "rgba(148, 163, 184, 0.1)",
            color: "#cbd5e1",
            border: "1px solid rgba(148, 163, 184, 0.2)",
            borderRadius: "8px",
            cursor: "pointer",
          }}
          title="Download QR Image"
        >
          <Download size={14} />
        </button>
      </div>

      {/* Raw Payload Preview Toggle / Summary */}
      <div
        style={{
          width: "100%",
          padding: "6px 8px",
          background: "rgba(0, 0, 0, 0.3)",
          borderRadius: "6px",
          fontSize: "0.7rem",
          color: "#94a3b8",
          fontFamily: "monospace",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
          textAlign: "center",
        }}
        title={value}
      >
        {value}
      </div>
    </div>
  );
};
