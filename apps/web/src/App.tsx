import React from "react";
import { BrowserRouter } from "react-router-dom";
import { AuthProvider } from "./context/AuthProvider.tsx";
import { ToastProvider } from "./components/ui/Toast.tsx";
import { StepUpProvider } from "./components/ssi/StepUpProvider.tsx";
import { AppRoutes } from "./routes/AppRoutes.tsx";
import { AppearanceProvider } from "./theme/AppearanceProvider.tsx";

export default function App() {
  return (
    <AppearanceProvider>
      <AuthProvider>
        <ToastProvider>
          <StepUpProvider>
            <BrowserRouter>
              <AppRoutes />
            </BrowserRouter>
          </StepUpProvider>
        </ToastProvider>
      </AuthProvider>
    </AppearanceProvider>
  );
}
