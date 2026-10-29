import React from "react";
import QRCode from "qrcode";
import { IdentifierText } from "./IdentifierText.tsx";

/** Renders a server-provided URI as a QR code, always with a text alternative. */
export const QrPanel: React.FC<{ value: string; label: string }> = ({ value, label }) => {
  const canvasRef = React.useRef<HTMLCanvasElement>(null);
  const [error, setError] = React.useState<string | null>(null);
  React.useEffect(() => {
    if (!canvasRef.current || !value) return;
    QRCode.toCanvas(canvasRef.current, value, { width: 220, margin: 1, color: { dark: "#182433", light: "#ffffff" } })
      .then(() => setError(null))
      .catch(() => setError("The QR code could not be drawn. Use the link below."));
  }, [value]);
  return (
    <figure className="d-flex flex-column align-items-center text-center gap-2 mb-0">
      <canvas ref={canvasRef} className="border rounded p-2 bg-white mw-100" role="img" aria-label={`QR code: ${label}`} />
      {error && <div className="invalid-feedback d-block">{error}</div>}
      <figcaption className="small text-secondary">{label}</figcaption>
      <IdentifierText value={value} label={`${label} link`} />
    </figure>
  );
};
