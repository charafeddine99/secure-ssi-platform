import React from "react";
import { IconMoon, IconSun } from "@tabler/icons-react";
import { useAppearance } from "./appearance.ts";

/** One-click dark/light switch, shown in every top bar. */
export const ModeToggle: React.FC<{ className?: string }> = ({ className }) => {
  const { appearance, update } = useAppearance();
  const dark = appearance.mode === "dark";
  return (
    <button
      type="button"
      className={["btn btn-icon ssi-mode-toggle", className ?? ""].filter(Boolean).join(" ")}
      onClick={() => update({ mode: dark ? "light" : "dark" })}
      aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
      title={dark ? "Light mode" : "Dark mode"}
    >
      {dark ? <IconSun size={20} aria-hidden="true" /> : <IconMoon size={20} aria-hidden="true" />}
    </button>
  );
};
