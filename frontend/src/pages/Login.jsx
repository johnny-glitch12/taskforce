import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { toast } from "sonner";
import { useAuth } from "@/App";
import { Lock, UserPlus, ArrowLeft } from "lucide-react";

export default function Login() {
  const [mode, setMode] = useState("login"); // "login" | "signup" | "forgot"
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [resetToken, setResetToken] = useState(null);
  const { login, register, user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (user) navigate("/studio", { replace: true });
  }, [user, navigate]);

  const API = process.env.REACT_APP_BACKEND_URL;

  const handleLogin = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const u = await login(email, password);
      toast.success(`Welcome back${u.name ? ", " + u.name : ""}.`);
      navigate("/studio");
    } catch (err) {
      toast.error(err.message || "Login failed.");
    }
    setSubmitting(false);
  };

  const handleSignup = async (e) => {
    e.preventDefault();
    if (password.length < 6) {
      toast.error("Password must be at least 6 characters.");
      return;
    }
    setSubmitting(true);
    try {
      const u = await register(email, password, name);
      toast.success(`Welcome, ${u.name}! Account created.`);
      navigate("/studio");
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
    } catch {
      toast.error("Network error.");
    }
    setSubmitting(false);
  };

  if (user) return null;

  return (
    <div className="min-h-[calc(100vh-60px)] flex items-center justify-center px-6">
      <div className="fixed top-[20%] left-1/2 -translate-x-1/2 w-[400px] h-[400px] rounded-full bg-[#8B5CF6]/[0.06] blur-[100px] pointer-events-none" />

      <div
        data-testid="auth-card"
        className="relative w-full max-w-sm bg-white/[0.03] border border-white/[0.08] rounded-2xl p-8 md:p-9 animate-fade-in-up backdrop-blur-sm"
        style={{ animationFillMode: "forwards" }}
      >
        {/* Header */}
        <div className="text-center mb-8">
          <div className="w-11 h-11 bg-[#8B5CF6]/10 rounded-xl flex items-center justify-center mx-auto mb-4">
            {mode === "signup" ? (
              <UserPlus size={18} className="text-[#8B5CF6]" />
            ) : (
              <Lock size={18} className="text-[#8B5CF6]" />
            )}
          </div>
          <h2
            data-testid="auth-title"
            className="text-xl font-semibold text-white tracking-tight"
            style={{ fontFamily: "'Outfit', sans-serif" }}
          >
            {mode === "login" ? "Sign in" : mode === "signup" ? "Create account" : "Reset password"}
          </h2>
          <p className="text-[13px] text-zinc-500 mt-1">
            {mode === "login"
              ? "Welcome back to Nova"
              : mode === "signup"
              ? "Join the AI agent economy"
              : "Enter your email to get a reset link"}
          </p>
        </div>

        {/* Login Form */}
        {mode === "login" && (
          <form onSubmit={handleLogin} data-testid="login-form" className="flex flex-col gap-5">
            <div>
              <label htmlFor="email" className="block text-[13px] text-zinc-500 mb-2">Email</label>
              <input
                id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                data-testid="login-email-input" placeholder="your@email.com"
                className="w-full bg-white/[0.04] border border-white/[0.08] text-white placeholder:text-zinc-600 focus:outline-none focus:border-[#8B5CF6]/50 transition-all py-3 px-4 text-[15px] rounded-xl"
                required
              />
            </div>
            <div>
              <label htmlFor="password" className="block text-[13px] text-zinc-500 mb-2">Password</label>
              <input
                id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                data-testid="login-password-input" placeholder="Enter password"
                className="w-full bg-white/[0.04] border border-white/[0.08] text-white placeholder:text-zinc-600 focus:outline-none focus:border-[#8B5CF6]/50 transition-all py-3 px-4 text-[15px] rounded-xl"
                required
              />
            </div>
            <button
              type="submit" data-testid="login-submit-btn"
              className="mt-2 w-full py-3.5 bg-[#8B5CF6] text-white text-[14px] font-medium rounded-full hover:bg-[#A78BFA] transition-all duration-300 shadow-[0_0_20px_rgba(139,92,246,0.25)] hover:shadow-[0_0_35px_rgba(139,92,246,0.4)] disabled:opacity-50"
              disabled={submitting}
            >
              {submitting ? "Signing in..." : "Sign in"}
            </button>
            <div className="flex items-center justify-between mt-1">
              <button
                type="button" data-testid="switch-to-signup-btn"
                onClick={() => { setMode("signup"); setResetToken(null); }}
                className="text-[12px] text-[#A78BFA] hover:text-[#C084FC] transition-colors"
              >
                Create account
              </button>
              <button
                type="button" data-testid="switch-to-forgot-btn"
                onClick={() => { setMode("forgot"); setResetToken(null); }}
                className="text-[12px] text-zinc-500 hover:text-zinc-300 transition-colors"
              >
                Forgot password?
              </button>
            </div>
          </form>
        )}

        {/* Signup Form */}
        {mode === "signup" && (
          <form onSubmit={handleSignup} data-testid="signup-form" className="flex flex-col gap-5">
            <div>
              <label htmlFor="name" className="block text-[13px] text-zinc-500 mb-2">Name</label>
              <input
                id="name" type="text" value={name} onChange={(e) => setName(e.target.value)}
                data-testid="signup-name-input" placeholder="Your name"
                className="w-full bg-white/[0.04] border border-white/[0.08] text-white placeholder:text-zinc-600 focus:outline-none focus:border-[#8B5CF6]/50 transition-all py-3 px-4 text-[15px] rounded-xl"
              />
            </div>
            <div>
              <label htmlFor="s-email" className="block text-[13px] text-zinc-500 mb-2">Email</label>
              <input
                id="s-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                data-testid="signup-email-input" placeholder="your@email.com"
                className="w-full bg-white/[0.04] border border-white/[0.08] text-white placeholder:text-zinc-600 focus:outline-none focus:border-[#8B5CF6]/50 transition-all py-3 px-4 text-[15px] rounded-xl"
                required
              />
            </div>
            <div>
              <label htmlFor="s-password" className="block text-[13px] text-zinc-500 mb-2">Password</label>
              <input
                id="s-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                data-testid="signup-password-input" placeholder="Min 6 characters"
                className="w-full bg-white/[0.04] border border-white/[0.08] text-white placeholder:text-zinc-600 focus:outline-none focus:border-[#8B5CF6]/50 transition-all py-3 px-4 text-[15px] rounded-xl"
                required minLength={6}
              />
            </div>
            <button
              type="submit" data-testid="signup-submit-btn"
              className="mt-2 w-full py-3.5 bg-[#8B5CF6] text-white text-[14px] font-medium rounded-full hover:bg-[#A78BFA] transition-all duration-300 shadow-[0_0_20px_rgba(139,92,246,0.25)] hover:shadow-[0_0_35px_rgba(139,92,246,0.4)] disabled:opacity-50"
              disabled={submitting}
            >
              {submitting ? "Creating account..." : "Create account"}
            </button>
            <button
              type="button" data-testid="switch-to-login-btn"
              onClick={() => setMode("login")}
              className="flex items-center justify-center gap-1.5 text-[12px] text-zinc-500 hover:text-zinc-300 transition-colors mt-1"
            >
              <ArrowLeft size={12} /> Back to sign in
            </button>
          </form>
        )}

        {/* Forgot Password Form */}
        {mode === "forgot" && (
          <div data-testid="forgot-form-wrapper">
            {!resetToken ? (
              <form onSubmit={handleForgotPassword} data-testid="forgot-form" className="flex flex-col gap-5">
                <div>
                  <label htmlFor="f-email" className="block text-[13px] text-zinc-500 mb-2">Email</label>
                  <input
                    id="f-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                    data-testid="forgot-email-input" placeholder="your@email.com"
                    className="w-full bg-white/[0.04] border border-white/[0.08] text-white placeholder:text-zinc-600 focus:outline-none focus:border-[#8B5CF6]/50 transition-all py-3 px-4 text-[15px] rounded-xl"
                    required
                  />
                </div>
                <button
                  type="submit" data-testid="forgot-submit-btn"
                  className="mt-2 w-full py-3.5 bg-[#8B5CF6] text-white text-[14px] font-medium rounded-full hover:bg-[#A78BFA] transition-all duration-300 shadow-[0_0_20px_rgba(139,92,246,0.25)] hover:shadow-[0_0_35px_rgba(139,92,246,0.4)] disabled:opacity-50"
                  disabled={submitting}
                >
                  {submitting ? "Sending..." : "Send reset link"}
                </button>
                <button
                  type="button" onClick={() => setMode("login")}
                  className="flex items-center justify-center gap-1.5 text-[12px] text-zinc-500 hover:text-zinc-300 transition-colors mt-1"
                >
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
    if (newPassword.length < 6) {
      toast.error("Password must be at least 6 characters.");
      return;
    }
    setSubmitting(true);
    try {
      const res = await fetch(`${API}/api/auth/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, new_password: newPassword }),
      });
      if (res.ok) {
        toast.success("Password reset! You can now sign in.");
        onSuccess();
      } else {
        const data = await res.json();
        toast.error(data.detail || "Reset failed.");
      }
    } catch {
      toast.error("Network error.");
    }
    setSubmitting(false);
  };

  return (
    <form onSubmit={handleReset} data-testid="reset-form" className="flex flex-col gap-5">
      <div className="bg-[#8B5CF6]/5 border border-[#8B5CF6]/20 rounded-xl p-3">
        <p className="text-[11px] text-[#A78BFA] mb-1">Reset Token (demo)</p>
        <p className="text-[12px] text-zinc-400 font-mono break-all">{token}</p>
      </div>
      <div>
        <label htmlFor="new-password" className="block text-[13px] text-zinc-500 mb-2">New Password</label>
        <input
          id="new-password" type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)}
          data-testid="reset-password-input" placeholder="Min 6 characters"
          className="w-full bg-white/[0.04] border border-white/[0.08] text-white placeholder:text-zinc-600 focus:outline-none focus:border-[#8B5CF6]/50 transition-all py-3 px-4 text-[15px] rounded-xl"
          required minLength={6}
        />
      </div>
      <button
        type="submit" data-testid="reset-submit-btn"
        className="mt-2 w-full py-3.5 bg-[#8B5CF6] text-white text-[14px] font-medium rounded-full hover:bg-[#A78BFA] transition-all duration-300 shadow-[0_0_20px_rgba(139,92,246,0.25)] hover:shadow-[0_0_35px_rgba(139,92,246,0.4)] disabled:opacity-50"
        disabled={submitting}
      >
        {submitting ? "Resetting..." : "Set new password"}
      </button>
    </form>
  );
}
