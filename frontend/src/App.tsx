import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/layout/Layout";
import LoginPage from "./pages/LoginPage";
import SignupPage from "./pages/SignupPage";
import ForgotPasswordPage from "./pages/ForgotPasswordPage";
import DashboardPage from "./pages/DashboardPage";
import ResumePage from "./pages/ResumePage";
import JobsPage from "./pages/JobsPage";
import ApplicationsPage from "./pages/ApplicationsPage";
import ApplicationDetailsPage from "./pages/ApplicationDetailsPage";
import CoverLetterPage from "./pages/CoverLetterPage";
import InterviewPrepPage from "./pages/InterviewPrepPage";
import AutomationPage from "./pages/AutomationPage";
import AdminPage from "./pages/AdminPage";
import NotificationsPage from "./pages/NotificationsPage";
import JobIntelPage from "./pages/JobIntelPage";
import CareerVaultPage from "./pages/CareerVaultPage";
import NotFoundPage from "./pages/NotFoundPage";
import { useAuthStore } from "./store/authStore";
import ProtectedRoute from "./components/auth/ProtectedRoute";

export default function App() {
  const token = useAuthStore((s) => s.token);

  return (
    <Routes>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route
        path="/login"
        element={token ? <Navigate to="/dashboard" /> : <LoginPage />}
      />
      <Route
        path="/signup"
        element={token ? <Navigate to="/dashboard" /> : <SignupPage />}
      />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/resume" element={<ResumePage />} />
          <Route path="/jobs" element={<JobsPage />} />
          <Route path="/vault" element={<CareerVaultPage />} />
          <Route path="/intel" element={<JobIntelPage />} />
          <Route path="/applications" element={<ApplicationsPage />} />
          <Route path="/applications/:id" element={<ApplicationDetailsPage />} />
          <Route path="/cover-letters" element={<CoverLetterPage />} />
          <Route path="/interview-prep" element={<InterviewPrepPage />} />
          <Route path="/automation" element={<AutomationPage />} />
          <Route path="/notifications" element={<NotificationsPage />} />
          <Route path="/admin" element={<AdminPage />} />
        </Route>
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
