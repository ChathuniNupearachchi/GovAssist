import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { Home } from "./pages/Home";
import { PlanAudit } from "./pages/PlanAudit";
import { RuleComparison } from "./pages/RuleComparison";
import { RuleReview } from "./pages/RuleReview";
import { ServiceDetail } from "./pages/ServiceDetail";
import { Services } from "./pages/Services";
import { SignIn } from "./pages/SignIn";
import { SignUp } from "./pages/SignUp";
import { Sources } from "./pages/Sources";

// admin-dashboard change, task 9.3 — navigation between home, rule
// review, service catalog, source catalog, and the outdated-plan view.
export function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/signin" element={<SignIn />} />
        <Route path="/signup" element={<SignUp />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Home />
            </ProtectedRoute>
          }
        />
        <Route
          path="/rules"
          element={
            <ProtectedRoute>
              <RuleReview />
            </ProtectedRoute>
          }
        />
        <Route
          path="/rules/:id"
          element={
            <ProtectedRoute>
              <RuleComparison />
            </ProtectedRoute>
          }
        />
        <Route
          path="/services"
          element={
            <ProtectedRoute>
              <Services />
            </ProtectedRoute>
          }
        />
        <Route
          path="/services/:id"
          element={
            <ProtectedRoute>
              <ServiceDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/sources"
          element={
            <ProtectedRoute>
              <Sources />
            </ProtectedRoute>
          }
        />
        <Route
          path="/plans"
          element={
            <ProtectedRoute>
              <PlanAudit />
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  );
}
