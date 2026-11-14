import React from "react";
import ReactDOM from "react-dom/client";
import "@fontsource/inter-tight/400.css";
import "@fontsource/inter-tight/500.css";
import "@fontsource/inter-tight/600.css";
import "@fontsource/inter-tight/700.css";
import App from "./App";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "./style.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={new QueryClient()}><App /></QueryClientProvider>
  </React.StrictMode>,
);
