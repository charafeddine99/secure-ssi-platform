import React from "react";
import { BrowserRouter } from "react-router-dom";
import { AuthProvider } from "./context/AuthProvider.tsx";
import { ToastProvider } from "./components/ui/Toast.tsx";
import { AppRoutes } from "./routes/AppRoutes.tsx";
import { AppearanceProvider } from "./theme/AppearanceProvider.tsx";

export default function App() {
  return (
    <AppearanceProvider>
      <AuthProvider>
        <ToastProvider>
          <BrowserRouter>
            <AppRoutes />
          </BrowserRouter>
        </ToastProvider>
      </AuthProvider>
    </AppearanceProvider>
  );
}
