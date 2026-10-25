import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";

class DashboardErrorBoundary extends React.Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <main style={{ padding: 32, color: "#eadbc0", fontFamily: "Georgia, serif" }} role="alert">
          <h1>Dashboard could not load</h1>
          <p>{this.state.error.message}</p>
        </main>
      );
    }
    return this.props.children;
  }
}

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <DashboardErrorBoundary><App /></DashboardErrorBoundary>
  </React.StrictMode>
);
