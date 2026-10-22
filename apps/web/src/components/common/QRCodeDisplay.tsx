import React, { useEffect, useRef, useState } from "react";
import QRCode from "qrcode";
import { Check, Copy, Download } from "lucide-react";

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
  const [copyError, setCopyError] = useState<string | null>(null);

  useEffect(() => {
    if (canvasRef.current && value) {
      QRCode.toCanvas(canvasRef.current, value, {
        width: size,
        margin: 2,
        color: { dark: "#0f172a", light: "#ffffff" },
      }, (error) => {
        if (error) console.error("QR Code generation error:", error);
      });
    }
  }, [value, size]);

  const handleCopy = async () => {
    setCopyError(null);
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopyError("Copy is unavailable in this browser. Scan the QR code instead.");
    }
  };

  const handleDownload = () => {
    if (!canvasRef.current) return;
    const url = canvasRef.current.toDataURL("image/png");
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "secure-ssi-request-qr.png";
    anchor.click();
  };

  return (
    <section className="qr-code-display" aria-label={title || "QR code"}>
      {title && <header className="qr-code-display__heading"><h3>{title}</h3>{subtitle && <p>{subtitle}</p>}</header>}
      <div className="qr-code-display__canvas"><canvas ref={canvasRef} role="img" aria-label={title ? title + " QR code" : "QR code"} /></div>
      <div className="qr-code-display__actions">
        <button className="workspace-secondary-action" type="button" onClick={() => void handleCopy()}>{copied ? <Check size={15} aria-hidden="true" /> : <Copy size={15} aria-hidden="true" />}{copied ? "Copied" : "Copy URI"}</button>
        <button className="qr-code-display__download" type="button" onClick={handleDownload} aria-label="Download QR code" title="Download QR code"><Download size={16} aria-hidden="true" /></button>
      </div>
      {copyError && <p className="qr-code-display__error" role="status">{copyError}</p>}
      <details className="qr-code-display__payload">
        <summary>Show request URI</summary>
        <code>{value}</code>
      </details>
    </section>
  );
};
