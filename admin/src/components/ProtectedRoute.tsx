import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth";
import { NavBar } from "./NavBar";

// admin-dashboard change, task 9.2 — redirect-to-signin for an
// expired/missing token. `useAuth`'s state already goes false the
// moment any API call gets a 401 (see api.ts's `request`), so a token
// that expires mid-session bounces here on the next navigation/request,
// not only on initial load.
export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return <Navigate to="/signin" replace />;
  }

  return (
    <div className="layout">
      <NavBar />
      <main className="content">{children}</main>
    </div>
  );
}
