import React from "react";

/**
 * Viewer appearance preferences, applied as Tabler theme attributes on <html>
 * (data-bs-theme, data-bs-theme-primary, data-bs-theme-base) plus the Secure SSI
 * background and corner-radius attributes. Stored per browser only.
 */
export type ColorMode = "dark" | "light";
export type PrimaryColor = "indigo" | "blue" | "azure" | "teal" | "purple" | "green" | "orange" | "red";
export type BasePalette = "slate" | "zinc" | "gray" | "neutral" | "stone";
export type Radius = "sharp" | "default" | "round";
export type Backdrop = "aurora" | "network" | "grid" | "plain";

export interface Appearance {
  mode: ColorMode;
  primary: PrimaryColor;
  base: BasePalette;
  radius: Radius;
  backdrop: Backdrop;
}

export const DEFAULT_APPEARANCE: Appearance = {
  mode: "dark",
  primary: "indigo",
  base: "slate",
  radius: "default",
  backdrop: "aurora",
};

export const PRIMARY_OPTIONS: PrimaryColor[] = ["indigo", "blue", "azure", "teal", "purple", "green", "orange", "red"];
export const BASE_OPTIONS: BasePalette[] = ["slate", "zinc", "gray", "neutral", "stone"];
export const RADIUS_OPTIONS: Array<{ value: Radius; label: string }> = [
  { value: "sharp", label: "Sharp" },
  { value: "default", label: "Default" },
  { value: "round", label: "Round" },
];
export const BACKDROP_OPTIONS: Array<{ value: Backdrop; label: string }> = [
  { value: "aurora", label: "Aurora" },
  { value: "network", label: "Trust network" },
  { value: "grid", label: "Grid" },
  { value: "plain", label: "Plain" },
];

// v2: the cinematic dark default applies once to everyone after the redesign.
const STORAGE_KEY = "ssi_appearance_v2";

function isOneOf<T extends string>(value: unknown, options: readonly T[]): value is T {
  return typeof value === "string" && (options as readonly string[]).includes(value);
}

export function readAppearance(): Appearance {
  try {
    const raw = globalThis.localStorage?.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_APPEARANCE;
    const parsed = JSON.parse(raw) as Partial<Record<keyof Appearance, unknown>>;
    return {
      mode: isOneOf(parsed.mode, ["dark", "light"] as const) ? parsed.mode : DEFAULT_APPEARANCE.mode,
      primary: isOneOf(parsed.primary, PRIMARY_OPTIONS) ? parsed.primary : DEFAULT_APPEARANCE.primary,
      base: isOneOf(parsed.base, BASE_OPTIONS) ? parsed.base : DEFAULT_APPEARANCE.base,
      radius: isOneOf(parsed.radius, RADIUS_OPTIONS.map((o) => o.value)) ? parsed.radius : DEFAULT_APPEARANCE.radius,
      backdrop: isOneOf(parsed.backdrop, BACKDROP_OPTIONS.map((o) => o.value)) ? parsed.backdrop : DEFAULT_APPEARANCE.backdrop,
    };
  } catch {
    return DEFAULT_APPEARANCE;
  }
}

export function storeAppearance(value: Appearance): void {
  try {
    globalThis.localStorage?.setItem(STORAGE_KEY, JSON.stringify(value));
  } catch {
    // Storage can be unavailable (private mode); the choice then lasts for this page only.
  }
}

export function applyAppearance(value: Appearance): void {
  const root = document.documentElement;
  root.setAttribute("data-bs-theme", value.mode);
  root.setAttribute("data-bs-theme-primary", value.primary);
  root.setAttribute("data-bs-theme-base", value.base);
  root.setAttribute("data-ssi-radius", value.radius);
  root.setAttribute("data-ssi-backdrop", value.backdrop);
}

export type ArtArea = "public" | "wallet" | "issuer" | "verifier" | "guardian" | "admin";

/** Picks the background illustration for the current workspace from the route. */
export function areaForPath(pathname: string): ArtArea {
  if (pathname.startsWith("/guardian")) return "guardian";
  if (pathname.startsWith("/wallet") || pathname.startsWith("/credentials") || pathname.startsWith("/consent")) return "wallet";
  if (pathname.startsWith("/issuer")) return "issuer";
  if (pathname.startsWith("/verifier")) return "verifier";
  if (pathname.startsWith("/admin")) return "admin";
  return "public";
}

/** Sets html[data-ssi-area] so the header band and page scene show the matching illustration. */
export function useArtArea(area: ArtArea): void {
  React.useEffect(() => {
    document.documentElement.setAttribute("data-ssi-area", area);
  }, [area]);
}

export interface AppearanceContextValue {
  appearance: Appearance;
  update: (patch: Partial<Appearance>) => void;
  reset: () => void;
  panelOpen: boolean;
  setPanelOpen: (open: boolean) => void;
}

export const AppearanceContext = React.createContext<AppearanceContextValue | null>(null);

export function useAppearance(): AppearanceContextValue {
  const value = React.useContext(AppearanceContext);
  if (!value) throw new Error("useAppearance must be used inside <AppearanceProvider>.");
  return value;
}
