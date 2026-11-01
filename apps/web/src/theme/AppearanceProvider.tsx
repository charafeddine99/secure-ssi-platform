import React from "react";
import { AppearancePanel } from "./AppearancePanel.tsx";
import {
  AppearanceContext,
  DEFAULT_APPEARANCE,
  applyAppearance,
  readAppearance,
  storeAppearance,
  type Appearance,
} from "./appearance.ts";

export const AppearanceProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [appearance, setAppearance] = React.useState<Appearance>(readAppearance);
  const [panelOpen, setPanelOpen] = React.useState(false);

  React.useLayoutEffect(() => {
    applyAppearance(appearance);
    storeAppearance(appearance);
  }, [appearance]);

  const value = React.useMemo(() => ({
    appearance,
    update: (patch: Partial<Appearance>) => setAppearance((current) => ({ ...current, ...patch })),
    reset: () => setAppearance(DEFAULT_APPEARANCE),
    panelOpen,
    setPanelOpen,
  }), [appearance, panelOpen]);

  return (
    <AppearanceContext.Provider value={value}>
      <div className="ssi-scene" aria-hidden="true" />
      {children}
      <AppearancePanel />
    </AppearanceContext.Provider>
  );
};
