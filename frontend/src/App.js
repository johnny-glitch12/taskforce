import { useState, useEffect, createContext, useContext, useCallback } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { Toaster } from "sonner";
import { ThemeProvider } from "@/lib/theme";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import Home from "@/pages/Home";
import Login from "@/pages/Login";
import Academy from "@/pages/Academy";
import Marketplace from "@/pages/Marketplace";
import Studio from "@/pages/Studio";
import CreatorProfile from "@/pages/CreatorProfile";
import AgentDetail from "@/pages/AgentDetail";
import PaymentSuccess from "@/pages/PaymentSuccess";
import Dashboard from "@/pages/Dashboard";
import CsdropDashboard from "@/pages/CsdropDashboard";
import SecurityDashboard from "@/pages/SecurityDashboard";
import OverwatchDashboard from "@/pages/OverwatchDashboard";
import Pricing from "@/pages/Pricing";
import CreatorDashboard from "@/pages/CreatorDashboard";
import CredentialsVault from "@/pages/CredentialsVault";
import Leaderboard from "@/pages/Leaderboard";
import ComingSoon from "@/pages/ComingSoon";
import ComingSoonLanding from "@/pages/ComingSoonLanding";
import Credits from "@/pages/Credits";
import MyDeployments from "@/pages/MyDeployments";
import UsageMonitor from "@/pages/UsageMonitor";
import VibeBuildPage from "@/pages/VibeBuildPage";
import ExternalAgents from "@/pages/ExternalAgents";
import HostingPlans from "@/pages/HostingPlans";
import BountyBoard from "@/pages/BountyBoard";
import BountyDetail from "@/pages/BountyDetail";
import Payouts from "@/pages/Payouts";
import CreatorEarnings from "@/pages/CreatorEarnings";
import ApiKeys from "@/pages/ApiKeys";
import ListingDetail from "@/pages/ListingDetail";
import OnboardingModal from "@/components/OnboardingModal";

const API = process.env.REACT_APP_BACKEND_URL;

export const AuthContext = createContext(null);

export function useAuth() {
  return useContext(AuthContext);
}

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

/** Admin-only route — non-admins (including unauthenticated) see ComingSoon. */
function AdminGate({ children, feature, subtitle }) {
  const { isAdmin, loading } = useAuth();
  if (loading) return null;
  if (!isAdmin) return <ComingSoon feature={feature} subtitle={subtitle} />;
  return children;
}

function App() {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(() => localStorage.getItem("taskforce_token"));
  const [loading, setLoading] = useState(true);

  const validateToken = useCallback(async () => {
    const stored = localStorage.getItem("taskforce_token");
    if (!stored) { setLoading(false); return; }
    try {
      const res = await fetch(`${API}/api/auth/me`, {
        headers: { Authorization: `Bearer ${stored}` },
      });
      if (res.ok) {
        const data = await res.json();
        setUser(data);
        setToken(stored);
      } else {
        localStorage.removeItem("taskforce_token");
        setToken(null);
        setUser(null);
      }
    } catch {
      localStorage.removeItem("taskforce_token");
      setToken(null);
      setUser(null);
    }
    setLoading(false);
  }, []);

  useEffect(() => { validateToken(); }, [validateToken]);

  const login = async (email, password) => {
    const res = await fetch(`${API}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Login failed");
    }
    const data = await res.json();
    localStorage.setItem("taskforce_token", data.token);
    setToken(data.token);
    setUser(data.user);
    return data.user;
  };

  const register = async (email, password, name) => {
    const res = await fetch(`${API}/api/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, name }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Registration failed");
    }
    const data = await res.json();
    localStorage.setItem("taskforce_token", data.token);
    setToken(data.token);
    setUser(data.user);
    return data.user;
  };

  const logout = () => {
    localStorage.removeItem("taskforce_token");
    setToken(null);
    setUser(null);
  };

  const isAdmin = user?.role === "admin";

  return (
    <AuthContext.Provider value={{ user, token, isAdmin, loading, login, register, logout }}>
      <ThemeProvider>
        <BrowserRouter>
          <AppShell />
        </BrowserRouter>
      </ThemeProvider>
    </AuthContext.Provider>
  );
}

/** Routes considered "public" (always accessible even when SITE_LOCKED=true). */
const AUTH_ROUTES = ["/login", "/auth/login", "/auth/register", "/auth/forgot-password", "/auth/reset-password"];

/** Auto-shows OnboardingModal once per user (first login after register). */
function OnboardingGate() {
  const { token, user } = useAuth();
  const [show, setShow] = useState(false);
  useEffect(() => {
    if (!token || !user || user.role === "admin") return;
    fetch(`${API}/api/onboarding/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.json())
      .then((d) => { if (d && !d.onboarded) setShow(true); })
      .catch(() => {});
  }, [token, user]);
  if (!show) return null;
  return <OnboardingModal onClose={() => setShow(false)} />;
}

function AppShell() {
  const { user, loading } = useAuth();
  const location = useLocation();
  const siteLocked = process.env.REACT_APP_SITE_LOCKED === "true";
  const isAuthRoute = AUTH_ROUTES.some((p) => location.pathname.startsWith(p));
  const shouldGate = siteLocked && !loading && !user;

  // 🛑 Site locked + unauth + not on /login → show ComingSoonLanding ONLY (no Navbar/Footer)
  if (shouldGate && !isAuthRoute) {
    return (
      <>
        <Toaster
          position="bottom-right"
          toastOptions={{
            style: {
              background: "rgba(0,0,0,0.95)",
              backdropFilter: "blur(12px)",
              border: "1px solid #1a1a1e",
              color: "#e4e4e7",
              fontFamily: "'JetBrains Mono', monospace",
              borderRadius: "2px",
              fontSize: "12px",
            },
          }}
        />
        <ComingSoonLanding />
      </>
    );
  }

  // 🔐 Site locked + unauth + on auth route → render ONLY Login (focused, no Navbar/Footer)
  if (shouldGate && isAuthRoute) {
    return (
      <>
        <Toaster position="bottom-right" />
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/auth/login" element={<Login />} />
          <Route path="/auth/register" element={<Login />} />
          <Route path="/auth/forgot-password" element={<Login />} />
          <Route path="/auth/reset-password" element={<Login />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </>
    );
  }

  // ✅ Normal full app shell (user is logged in OR site is unlocked)
  return (
    <div className="min-h-screen t-bg flex flex-col" style={{ transition: "background-color 0.3s ease" }}>
      <Navbar />
      {user && <OnboardingGate />}
      <Toaster
        position="bottom-right"
        toastOptions={{
          style: {
            background: "var(--toast-bg)",
            backdropFilter: "blur(12px)",
            border: "1px solid var(--border)",
            color: "var(--toast-text)",
            fontFamily: "'JetBrains Mono', monospace",
            borderRadius: "2px",
            fontSize: "12px",
          },
        }}
      />
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<Login />} />
          <Route path="/auth/login" element={<Login />} />
          <Route path="/auth/register" element={<Login />} />
          <Route path="/auth/forgot-password" element={<Login />} />
          <Route path="/auth/reset-password" element={<Login />} />
          <Route
            path="/academy"
            element={<AdminGate feature="The Academy" subtitle="Free training videos, drops, and operator playbooks land here when we publicly open Task Force AI." />}
          />
          <Route path="/pricing" element={<Pricing />} />
          <Route path="/exchange" element={<Marketplace />} />
          <Route path="/leaderboard" element={<Leaderboard />} />
          <Route path="/marketplace" element={<Marketplace />} />
          <Route path="/agent/:id" element={<AgentDetail />} />
          <Route path="/creator/:id" element={<CreatorProfile />} />
          <Route path="/payment/success" element={<PaymentSuccess />} />
          <Route
            path="/armory"
            element={
              <AdminGate
                feature="The Armory"
                subtitle="Visual + code bot builder is in private beta. Public access opens with the v1 launch — join the waitlist below."
              >
                <Studio />
              </AdminGate>
            }
          />
          <Route
            path="/studio"
            element={
              <AdminGate feature="The Armory">
                <Studio />
              </AdminGate>
            }
          />
          <Route path="/credits" element={<ProtectedRoute><Credits /></ProtectedRoute>} />
          <Route path="/build" element={<ProtectedRoute><VibeBuildPage /></ProtectedRoute>} />
          <Route path="/external-agents" element={<ProtectedRoute><ExternalAgents /></ProtectedRoute>} />
          <Route path="/hosting" element={<ProtectedRoute><HostingPlans /></ProtectedRoute>} />
          <Route path="/bounties" element={<BountyBoard />} />
          <Route path="/bounties/:id" element={<ProtectedRoute><BountyDetail /></ProtectedRoute>} />
          <Route path="/payouts" element={<ProtectedRoute><Payouts /></ProtectedRoute>} />
          <Route path="/earnings" element={<ProtectedRoute><CreatorEarnings /></ProtectedRoute>} />
          <Route path="/keys" element={<ProtectedRoute><ApiKeys /></ProtectedRoute>} />
          <Route path="/listing/:id" element={<ListingDetail />} />
          <Route path="/my-deployments" element={<ProtectedRoute><MyDeployments /></ProtectedRoute>} />
          <Route path="/my-deployments/:id/monitor" element={<ProtectedRoute><UsageMonitor /></ProtectedRoute>} />
          <Route path="/deployments" element={<Navigate to="/my-deployments" replace />} />
          <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
          <Route path="/dashboard/csdrop" element={<ProtectedRoute><CsdropDashboard /></ProtectedRoute>} />
          <Route path="/security" element={<ProtectedRoute><SecurityDashboard /></ProtectedRoute>} />
          <Route path="/overwatch" element={<ProtectedRoute><OverwatchDashboard /></ProtectedRoute>} />
          <Route path="/creator" element={<ProtectedRoute><CreatorDashboard /></ProtectedRoute>} />
          <Route path="/credentials" element={<ProtectedRoute><CredentialsVault /></ProtectedRoute>} />
        </Routes>
      </main>
      <Footer />
    </div>
  );
}

export default App;
