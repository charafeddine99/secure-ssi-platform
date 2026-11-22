import React from "react";
import platformBackgroundVideo from "../pages/public/v1.mp4";
import { AppearancePanel } from "./AppearancePanel.tsx";
import {
  AppearanceContext,
  DEFAULT_APPEARANCE,
  applyAppearance,
  readAppearance,
  storeAppearance,
  type Appearance,
} from "./appearance.ts";

const VideoBackdrop: React.FC = () => {
  const videoRef = React.useRef<HTMLVideoElement>(null);

  React.useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    video.defaultMuted = true;
    video.muted = true;

    const mediaQuery = globalThis.matchMedia?.("(prefers-reduced-motion: reduce)");
    const syncPlayback = () => {
      if (mediaQuery?.matches) {
        video.pause();
      } else {
        void video.play().catch(() => {
          // Autoplay may be blocked by browser policy; keep first frame visible.
        });
      }
    };

    syncPlayback();
    mediaQuery?.addEventListener?.("change", syncPlayback);
    return () => mediaQuery?.removeEventListener?.("change", syncPlayback);
  }, []);

  return (
    <div className="ssi-video-backdrop d-print-none" aria-hidden="true">
      <video
        ref={videoRef}
        className="ssi-video-backdrop-media"
        src={platformBackgroundVideo}
        autoPlay
        loop
        muted
        playsInline
        preload="auto"
        tabIndex={-1}
      />
      <div className="ssi-video-backdrop-scrim" />
    </div>
  );
};

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
      {appearance.backdrop === "video" && <VideoBackdrop />}
      <div className="ssi-scene" aria-hidden="true" />
      {children}
      <AppearancePanel />
    </AppearanceContext.Provider>
  );
};
