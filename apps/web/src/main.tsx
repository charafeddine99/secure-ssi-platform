import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { StatusPage } from "./pages/StatusPage";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode><StatusPage /></StrictMode>,
);
