import React from "react";
import { createPortal } from "react-dom";
import { IconMoon, IconSun } from "@tabler/icons-react";
import {
  BACKDROP_OPTIONS,
  BASE_OPTIONS,
  PRIMARY_OPTIONS,
  RADIUS_OPTIONS,
  useAppearance,
  type ColorMode,
} from "./appearance.ts";

function title(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

/** Tabler "Customize" offcanvas: colour mode, accent, base palette, radius and backdrop. */
export const AppearancePanel: React.FC = () => {
  const { appearance, update, reset, panelOpen, setPanelOpen } = useAppearance();
  const panelRef = React.useRef<HTMLDivElement>(null);
  const titleId = React.useId();

  React.useEffect(() => {
    if (!panelOpen) return;
    const opener = document.activeElement as HTMLElement | null;
    panelRef.current?.querySelector<HTMLElement>("button, input")?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setPanelOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      opener?.focus();
    };
  }, [panelOpen, setPanelOpen]);

  if (!panelOpen) return null;

  const modes: Array<{ value: ColorMode; label: string; icon: React.ReactNode }> = [
    { value: "dark", label: "Dark", icon: <IconMoon size={18} aria-hidden="true" /> },
    { value: "light", label: "Light", icon: <IconSun size={18} aria-hidden="true" /> },
  ];

  return createPortal(
    <>
      <div
        ref={panelRef}
        className="offcanvas offcanvas-end show ssi-appearance"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
      >
        <div className="offcanvas-header">
          <h2 id={titleId} className="offcanvas-title h3">Appearance</h2>
          <button type="button" className="btn-close" aria-label="Close" onClick={() => setPanelOpen(false)} />
        </div>
        <div className="offcanvas-body vstack gap-4">
          <fieldset>
            <legend className="form-label">Mode</legend>
            <div className="form-selectgroup form-selectgroup-boxes w-100">
              {modes.map((mode) => (
                <label key={mode.value} className="form-selectgroup-item flex-fill">
                  <input type="radio" name="ssi-mode" className="form-selectgroup-input" checked={appearance.mode === mode.value} onChange={() => update({ mode: mode.value })} />
                  <span className="form-selectgroup-label d-flex align-items-center justify-content-center gap-2 py-3">{mode.icon}{mode.label}</span>
                </label>
              ))}
            </div>
          </fieldset>

          <fieldset>
            <legend className="form-label">Accent colour</legend>
            <div className="row g-2">
              {PRIMARY_OPTIONS.map((color) => (
                <div key={color} className="col-auto">
                  <label className="form-colorinput" title={title(color)}>
                    <input type="radio" name="ssi-primary" className="form-colorinput-input" checked={appearance.primary === color} onChange={() => update({ primary: color })} />
                    <span className={`form-colorinput-color bg-${color}`} />
                    <span className="visually-hidden">{title(color)}</span>
                  </label>
                </div>
              ))}
            </div>
          </fieldset>

          <fieldset>
            <legend className="form-label">Background</legend>
            <div className="row g-2">
              {BACKDROP_OPTIONS.map((option) => (
                <div key={option.value} className="col-6">
                  <label className="form-selectgroup-item w-100">
                    <input type="radio" name="ssi-backdrop" className="form-selectgroup-input" checked={appearance.backdrop === option.value} onChange={() => update({ backdrop: option.value })} />
                    <span className="form-selectgroup-label p-2 d-block text-start">
                      <span className={`ssi-backdrop-preview ssi-backdrop-preview-${option.value}`} aria-hidden="true" />
                      <span className="d-block mt-2 small">{option.label}</span>
                    </span>
                  </label>
                </div>
              ))}
            </div>
          </fieldset>

          <fieldset>
            <legend className="form-label">Base palette</legend>
            <div className="form-selectgroup">
              {BASE_OPTIONS.map((base) => (
                <label key={base} className="form-selectgroup-item">
                  <input type="radio" name="ssi-base" className="form-selectgroup-input" checked={appearance.base === base} onChange={() => update({ base })} />
                  <span className="form-selectgroup-label">{title(base)}</span>
                </label>
              ))}
            </div>
          </fieldset>

          <fieldset>
            <legend className="form-label">Corners</legend>
            <div className="form-selectgroup">
              {RADIUS_OPTIONS.map((option) => (
                <label key={option.value} className="form-selectgroup-item">
                  <input type="radio" name="ssi-radius" className="form-selectgroup-input" checked={appearance.radius === option.value} onChange={() => update({ radius: option.value })} />
                  <span className="form-selectgroup-label">{option.label}</span>
                </label>
              ))}
            </div>
          </fieldset>
        </div>
        <div className="offcanvas-footer border-top p-3 d-flex gap-2">
          <button type="button" className="btn flex-fill" onClick={reset}>Reset</button>
          <button type="button" className="btn btn-primary flex-fill" onClick={() => setPanelOpen(false)}>Done</button>
        </div>
      </div>
      <div className="offcanvas-backdrop fade show" onClick={() => setPanelOpen(false)} aria-hidden="true" />
    </>,
    document.body,
  );
};
