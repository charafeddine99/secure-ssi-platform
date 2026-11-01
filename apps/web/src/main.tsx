import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource-variable/inter";
import "@tabler/core/dist/css/tabler.min.css";
import "@tabler/core/dist/css/tabler-themes.min.css";
import App from "./App.tsx";
import "./styles/app.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
