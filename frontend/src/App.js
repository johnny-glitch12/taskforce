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
import VibeBuildPage from "@/pages/VibeBuildPage"; // legacy — kept for direct linking; /build route removed
import ExternalAgents from "@/pages/ExternalAgents";
import HostingPlans from "@/pages/HostingPlans";
import BountyBoard from "@/pages/BountyBoard";
import BountyDetail from "@/pages/BountyDetail";
import Payouts from "@/pages/Payouts";
import CreatorEarnings from "@/pages/CreatorEarnings";
import ApiKeys from "@/pages/ApiKeys";
import ListingDetail from "@/pages/ListingDetail";
import Armory from "@/pages/Armory";
import EconomicsDashboard from "@/pages/EconomicsDashboard";
import MyApps from "@/pages/MyApps";
import AppViewer from "@/pages/AppViewer";
import BuilderMemory from "@/pages/BuilderMemory";
import MyAgents from "@/pages/MyAgents";
import AgentControlPanel from "@/pages/AgentControlPanel";
import OnboardingModal from "@/components/OnboardingModal";
import MemoryFirstTimeNotice from "@/components/MemoryFirstTimeNotice";
import { CreditProvider } from "@/lib/credits";

// API base URL: in preview/dev we hit a separate backend origin via REACT_APP_BACKEND_URL.
// In production single-container (Railway), the frontend is served by FastAPI on the
// SAME origin, so an empty string makes every fetch resolve to a relative `/api/...` path.
const API = process.env.REACT_APP_BACKEND_URL || "";

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

/** Owner-only route — even dev admins are denied. */
function OwnerGate({ children, feature, subtitle }) {
  const { isOwner, loading } = useAuth();
  if (loading) return null;
  if (!isOwner) return <ComingSoon feature={feature || "Owner Only"} subtitle={subtitle || "This area is restricted to platform owners."} />;
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

  const register = async (email, password, { username = "", name = "" } = {}) => {
    const res = await fetch(`${API}/api/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, username, name }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      // The new backend returns {detail: {error, details: [...]}} on 422.
      // Fall back to FastAPI's default {detail: [...]} or plain {detail: "..."}.
      const d = err?.detail;
      let msg = "Registration failed";
      if (typeof d === "string") msg = d;
      else if (d && Array.isArray(d.details)) msg = d.details.join(" ");
      else if (Array.isArray(d)) msg = d.map((e) => e?.msg || "").filter(Boolean).join(" ") || msg;
      else if (d && typeof d.msg === "string") msg = d.msg;
      throw new Error(msg);
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
  const isOwner = isAdmin && !!user?.is_owner;

  return (
    <AuthContext.Provider value={{ user, token, isAdmin, isOwner, loading, login, register, logout }}>
      <ThemeProvider>
        <CreditProvider>
          <BrowserRouter>
            <AppShell />
          </BrowserRouter>
        </CreditProvider>
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
  const hideFooter = location.pathname.startsWith("/armory");
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
          <Route path="/academy" element={<Academy />} />
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
              <ProtectedRoute>
                <>
                  <Armory />
                  <MemoryFirstTimeNotice />
                </>
              </ProtectedRoute>
            }
          />
          <Route
            path="/armory/workflows/:projectId"
            element={
              <AdminGate feature="Workflows Editor">
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
          {/* /build legacy route removed — Armory is the single builder now */}
          <Route path="/build" element={<Navigate to="/armory" replace />} />
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
          <Route path="/admin/economics" element={<OwnerGate feature="Platform Economics"><EconomicsDashboard /></OwnerGate>} />
          <Route path="/my-apps" element={<ProtectedRoute><MyApps /></ProtectedRoute>} />
          <Route path="/apps/:slug" element={<ProtectedRoute><AppViewer /></ProtectedRoute>} />
          {/* Prompt 31 Phase 2 — Agent Operations Hub */}
          <Route path="/my-agents" element={<ProtectedRoute><MyAgents /></ProtectedRoute>} />
          <Route path="/my-agents/:id" element={<ProtectedRoute><AgentControlPanel /></ProtectedRoute>} />
          <Route path="/settings/memory" element={<ProtectedRoute><BuilderMemory /></ProtectedRoute>} />
        </Routes>
      </main>
      {hideFooter ? null : <Footer />}
    </div>
  );
}

export default App;
