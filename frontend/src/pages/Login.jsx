import { useState, useEffect, useCallback } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useAuth } from "@/App";
import { Lock, UserPlus, ArrowLeft, Eye, EyeOff, CheckCircle2, XCircle } from "lucide-react";
import PasswordStrengthMeter, { scorePassword } from "@/components/PasswordStrengthMeter";
import UsernameField from "@/components/UsernameField";

// Whitelist for `?return=` redirect targets. We only honor SAME-ORIGIN paths
// starting with "/" and not "//" (which is protocol-relative and could leak).
// Auth routes themselves are excluded so we don't bounce users back to login.
const AUTH_PATH_PREFIXES = ["/login", "/auth/"];
function safeReturnPath(raw) {
  if (!raw || typeof raw !== "string") return null;
  if (!raw.startsWith("/") || raw.startsWith("//")) return null;
  if (AUTH_PATH_PREFIXES.some((p) => raw.startsWith(p))) return null;
  return raw;
}

export default function Login() {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [username, setUsername] = useState("");
  const [usernameStatus, setUsernameStatus] = useState({ available: false, reason: "idle" });
  const [name, setName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [resetToken, setResetToken] = useState(null);
  const { login, register, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const API = process.env.REACT_APP_BACKEND_URL || "";

  // Prompt 31 Phase 5 — honor ?return=<path> AND react-router `state.from`.
  const returnPath = (() => {
    try {
      const q = new URLSearchParams(location.search).get("return");
      const fromState = location.state && location.state.from;
      return safeReturnPath(q) || safeReturnPath(fromState) || null;
    } catch { return null; }
  })();

  const postAuthRedirect = useCallback((u) => {
    if (returnPath) { navigate(returnPath, { replace: true }); return; }
    if (u && u.client_id === "csdrop") { navigate("/dashboard/csdrop", { replace: true }); return; }
    navigate("/armory", { replace: true });
  }, [returnPath, navigate]);

  const handleUsernameStatus = useCallback((s) => setUsernameStatus(s), []);

  // Derived signup validity — gates the submit button.
  const pwd = scorePassword(password, username, email);
  const passwordsMatch = password.length > 0 && password === confirmPassword;
  const canSubmitSignup = !!email && !!username && usernameStatus.available && pwd.ok && passwordsMatch;

  useEffect(() => {
    if (user) postAuthRedirect(user);
  }, [user, postAuthRedirect]);

  const handleLogin = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const u = await login(email, password);
      toast.success(`Welcome back${u.name ? ", " + u.name : ""}.`);
      postAuthRedirect(u);
    } catch (err) {
      toast.error(err.message || "Login failed.");
    }
    setSubmitting(false);
  };

  const handleSignup = async (e) => {
    e.preventDefault();
    if (!canSubmitSignup) {
      // Surface the first concrete reason.
      if (!username) return toast.error("Pick a username.");
      if (!usernameStatus.available) return toast.error("Choose an available username.");
      if (!pwd.ok) return toast.error(pwd.rules.length ? "Password doesn't meet all requirements." : "Password must be at least 8 characters.");
      if (!passwordsMatch) return toast.error("Passwords don't match.");
      return;
    }
    setSubmitting(true);
    try {
      const u = await register(email, password, { username, name });
      toast.success(`Welcome, ${u.name}! Account created.`);
      postAuthRedirect(u);
    } catch (err) {
      toast.error(err.message || "Registration failed.");
    }
    setSubmitting(false);
  };

  const handleForgotPassword = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const res = await fetch(`${API}/api/auth/forgot-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const data = await res.json();
      if (data.reset_token) {
        setResetToken(data.reset_token);
        toast.success("Reset token generated. In production, this would be emailed.");
      } else {
        toast.info("If that email exists, a reset link has been sent.");
      }
    } catch { toast.error("Network error."); }
    setSubmitting(false);
  };

  if (user) return null;

  const inputCls = "w-full t-input focus:outline-none focus:border-cyan-400/50 transition-all py-3 px-4 text-[15px] rounded-xl";

  return (
    <div className="min-h-[calc(100vh-60px)] flex items-center justify-center px-6">
      <div className="fixed top-[20%] left-1/2 -translate-x-1/2 w-[400px] h-[400px] rounded-sm bg-cyan-400/[0.06] blur-[100px] pointer-events-none t-orb" />

      <div
        data-testid="auth-card"
        className="relative w-full max-w-sm rounded-sm p-8 md:p-9 animate-fade-in-up backdrop-blur-sm"
        style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', animationFillMode: "forwards" }}
      >
        {/* Header */}
        <div className="text-center mb-8">
          <div className="w-11 h-11 bg-cyan-400/10 rounded-xl flex items-center justify-center mx-auto mb-4">
            {mode === "signup" ? <UserPlus size={18} className="text-cyan-400" /> : <Lock size={18} className="text-cyan-400" />}
          </div>
          <h2 data-testid="auth-title" className="text-xl font-semibold t-text tracking-tight" style={{ fontFamily: "'Outfit', sans-serif" }}>
            {mode === "login" ? "Sign in" : mode === "signup" ? "Create account" : "Reset password"}
          </h2>
          <p className="text-[13px] t-text-sub mt-1">
            {mode === "login" ? "Welcome back, operative." : mode === "signup" ? "Join the AI execution economy." : "Enter your email to get a reset link."}
          </p>
        </div>

        {/* Login */}
        {mode === "login" && (
          <form onSubmit={handleLogin} data-testid="login-form" className="flex flex-col gap-5">
            <div>
              <label htmlFor="email" className="block text-[13px] t-text-sub mb-2">Email or Username</label>
              <input id="email" type="text" value={email} onChange={(e) => setEmail(e.target.value)} data-testid="login-email-input" placeholder="you@example.com or your_username" className={inputCls} style={{ border: '1px solid var(--input-border)' }} required autoComplete="username" />
            </div>
            <div>
              <label htmlFor="password" className="block text-[13px] t-text-sub mb-2">Password</label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  data-testid="login-password-input"
                  placeholder="Enter password"
                  className={inputCls}
                  style={{ border: '1px solid var(--input-border)', paddingRight: 40 }}
                  required
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  data-testid="login-password-toggle"
                  onClick={() => setShowPassword((s) => !s)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-cyan-400 transition-colors"
                >
                  {showPassword ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
            </div>
            <button type="submit" data-testid="login-submit-btn" className="mt-2 w-full py-3.5 bg-cyan-400 text-black text-[14px] font-bold rounded-sm hover:bg-cyan-300 transition-all duration-300 shadow-[0_0_20px_rgba(34,211,238,0.25)] hover:shadow-[0_0_35px_rgba(34,211,238,0.4)] disabled:opacity-50" disabled={submitting}>
              {submitting ? "Signing in..." : "Sign in"}
            </button>
            <div className="flex items-center justify-between mt-1">
              <button type="button" data-testid="switch-to-signup-btn" onClick={() => { setMode("signup"); setResetToken(null); }} className="text-[12px] text-cyan-300 hover:text-[#C084FC] transition-colors">Create account</button>
              <button type="button" data-testid="switch-to-forgot-btn" onClick={() => { setMode("forgot"); setResetToken(null); }} className="text-[12px] t-text-sub hover:t-text transition-colors">Forgot password?</button>
            </div>
          </form>
        )}

        {/* Signup */}
        {mode === "signup" && (
          <form onSubmit={handleSignup} data-testid="signup-form" className="flex flex-col gap-4">
            {/* Username (with live availability check) */}
            <div>
              <label htmlFor="s-username" className="block text-[13px] t-text-sub mb-2">Username</label>
              <UsernameField value={username} onChange={setUsername} onStatus={handleUsernameStatus} />
            </div>

            {/* Display name (optional, free-form) */}
            <div>
              <label htmlFor="name" className="block text-[13px] t-text-sub mb-2">Display Name <span className="text-zinc-600">(optional)</span></label>
              <input id="name" type="text" value={name} onChange={(e) => setName(e.target.value.slice(0, 80))} data-testid="signup-name-input" placeholder="What we call you in the UI" className={inputCls} style={{ border: '1px solid var(--input-border)' }} />
            </div>

            {/* Email */}
            <div>
              <label htmlFor="s-email" className="block text-[13px] t-text-sub mb-2">Email</label>
              <input id="s-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} data-testid="signup-email-input" placeholder="your@email.com" className={inputCls} style={{ border: '1px solid var(--input-border)' }} required />
            </div>

            {/* Password + strength meter + visibility toggle */}
            <div>
              <label htmlFor="s-password" className="block text-[13px] t-text-sub mb-2">Password</label>
              <div className="relative">
                <input
                  id="s-password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  data-testid="signup-password-input"
                  placeholder="At least 8 characters, mix of types"
                  className={inputCls}
                  style={{ border: '1px solid var(--input-border)', paddingRight: 40 }}
                  required
                  minLength={8}
                  maxLength={128}
                  autoComplete="new-password"
                />
                <button
                  type="button"
                  data-testid="signup-password-toggle"
                  onClick={() => setShowPassword((s) => !s)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-cyan-400 transition-colors"
                >
                  {showPassword ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
              <PasswordStrengthMeter value={password} username={username} email={email} testidPrefix="signup-pwd" />
            </div>

            {/* Confirm password + match indicator */}
            <div>
              <label htmlFor="s-confirm" className="block text-[13px] t-text-sub mb-2">Confirm Password</label>
              <div className="relative">
                <input
                  id="s-confirm"
                  type={showConfirm ? "text" : "password"}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  data-testid="signup-confirm-input"
                  placeholder="Re-enter password"
                  className={inputCls}
                  style={{ border: `1px solid ${confirmPassword && (passwordsMatch ? 'rgba(52,211,153,0.5)' : 'rgba(244,63,94,0.5)')}` || '1px solid var(--input-border)', paddingRight: 40 }}
                  required
                  maxLength={128}
                  autoComplete="new-password"
                />
                <button
                  type="button"
                  data-testid="signup-confirm-toggle"
                  onClick={() => setShowConfirm((s) => !s)}
                  aria-label={showConfirm ? "Hide password" : "Show password"}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-cyan-400 transition-colors"
                >
                  {showConfirm ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
              {confirmPassword && (
                <p
                  data-testid="signup-confirm-status"
                  className={`text-[10px] font-mono mt-1.5 tracking-wide flex items-center gap-1 ${passwordsMatch ? 'text-emerald-400' : 'text-rose-400'}`}
                >
                  {passwordsMatch ? <CheckCircle2 size={11} /> : <XCircle size={11} />}
                  {passwordsMatch ? "Passwords match" : "Passwords don't match"}
                </p>
              )}
            </div>

            <button
              type="submit"
              data-testid="signup-submit-btn"
              disabled={submitting || !canSubmitSignup}
              className="mt-2 w-full py-3.5 bg-cyan-400 text-black text-[14px] font-bold rounded-sm hover:bg-cyan-300 transition-all duration-300 shadow-[0_0_20px_rgba(34,211,238,0.25)] hover:shadow-[0_0_35px_rgba(34,211,238,0.4)] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {submitting ? "Creating account..." : "Create account"}
            </button>
            <button
              type="button"
              data-testid="switch-to-login-btn"
              onClick={() => setMode("login")}
              className="flex items-center justify-center gap-1.5 text-[12px] t-text-sub hover:t-text transition-colors mt-1"
            >
              <ArrowLeft size={12} /> Back to sign in
            </button>
          </form>
        )}

        {/* Forgot Password */}
        {mode === "forgot" && (
          <div data-testid="forgot-form-wrapper">
            {!resetToken ? (
              <form onSubmit={handleForgotPassword} data-testid="forgot-form" className="flex flex-col gap-5">
                <div>
                  <label htmlFor="f-email" className="block text-[13px] t-text-sub mb-2">Email</label>
                  <input id="f-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} data-testid="forgot-email-input" placeholder="your@email.com" className={inputCls} style={{ border: '1px solid var(--input-border)' }} required />
                </div>
                <button type="submit" data-testid="forgot-submit-btn" className="mt-2 w-full py-3.5 bg-cyan-400 text-black text-[14px] font-bold rounded-sm hover:bg-cyan-300 transition-all duration-300 shadow-[0_0_20px_rgba(34,211,238,0.25)] hover:shadow-[0_0_35px_rgba(34,211,238,0.4)] disabled:opacity-50" disabled={submitting}>
                  {submitting ? "Sending..." : "Send reset link"}
                </button>
                <button type="button" onClick={() => setMode("login")} className="flex items-center justify-center gap-1.5 text-[12px] t-text-sub hover:t-text transition-colors mt-1">
                  <ArrowLeft size={12} /> Back to sign in
                </button>
              </form>
            ) : (
              <ResetPasswordForm token={resetToken} API={API} onSuccess={() => { setMode("login"); setResetToken(null); }} />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function ResetPasswordForm({ token, API, onSuccess }) {
  const [newPassword, setNewPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleReset = async (e) => {
    e.preventDefault();
    if (newPassword.length < 6) { toast.error("Password must be at least 6 characters."); return; }
    setSubmitting(true);
    try {
      const res = await fetch(`${API}/api/auth/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, new_password: newPassword }),
      });
      if (res.ok) { toast.success("Password reset! You can now sign in."); onSuccess(); }
      else { const data = await res.json(); toast.error(data.detail || "Reset failed."); }
    } catch { toast.error("Network error."); }
    setSubmitting(false);
  };

  return (
    <form onSubmit={handleReset} data-testid="reset-form" className="flex flex-col gap-5">
      <div className="bg-cyan-400/5 border border-cyan-400/20 rounded-xl p-3">
        <p className="text-[11px] text-cyan-300 mb-1">Reset Token (demo)</p>
        <p className="text-[12px] t-text-mute font-mono break-all">{token}</p>
      </div>
      <div>
        <label htmlFor="new-password" className="block text-[13px] t-text-sub mb-2">New Password</label>
        <input id="new-password" type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} data-testid="reset-password-input" placeholder="Min 6 characters" className="w-full t-input focus:outline-none focus:border-cyan-400/50 transition-all py-3 px-4 text-[15px] rounded-xl" style={{ border: '1px solid var(--input-border)' }} required minLength={6} />
      </div>
      <button type="submit" data-testid="reset-submit-btn" className="mt-2 w-full py-3.5 bg-cyan-400 text-black text-[14px] font-bold rounded-sm hover:bg-cyan-300 transition-all duration-300 shadow-[0_0_20px_rgba(34,211,238,0.25)] hover:shadow-[0_0_35px_rgba(34,211,238,0.4)] disabled:opacity-50" disabled={submitting}>
        {submitting ? "Resetting..." : "Set new password"}
      </button>
    </form>
  );
}
