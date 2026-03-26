import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useAuth } from "@/App";
import { Lock } from "lucide-react";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const { login, isAdmin } = useAuth();
  const navigate = useNavigate();

  if (isAdmin) {
    navigate("/studio", { replace: true });
    return null;
  }

  const handleSubmit = (e) => {
    e.preventDefault();
    const success = login(email);
    if (success) {
      toast.success("Welcome to Nova Studio.");
      navigate("/studio");
    } else {
      toast.error("Currently in private beta. Please join the waitlist.");
    }
  };

  return (
    <div className="min-h-[calc(100vh-60px)] flex items-center justify-center px-6">
      {/* Subtle glow */}
      <div className="fixed top-[20%] left-1/2 -translate-x-1/2 w-[400px] h-[400px] rounded-full bg-[#8B5CF6]/[0.06] blur-[100px] pointer-events-none" />

      <div
        data-testid="login-card"
        className="relative w-full max-w-sm bg-white/[0.03] border border-white/[0.08] rounded-2xl p-8 md:p-9 animate-fade-in-up backdrop-blur-sm"
        style={{ animationFillMode: "forwards" }}
      >
        {/* Header */}
        <div className="text-center mb-8">
          <div className="w-11 h-11 bg-[#8B5CF6]/10 rounded-xl flex items-center justify-center mx-auto mb-4">
            <Lock size={18} className="text-[#8B5CF6]" />
          </div>
          <h2
            className="text-xl font-semibold text-white tracking-tight"
            style={{ fontFamily: "'Outfit', sans-serif" }}
          >
            Sign in
          </h2>
          <p className="text-[13px] text-zinc-500 mt-1">
            Private beta access
          </p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-5">
          {/* Email */}
          <div>
            <label
              htmlFor="email"
              className="block text-[13px] text-zinc-500 mb-2"
            >
              Email
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              data-testid="login-email-input"
              placeholder="admin@nova.ai"
              className="w-full bg-white/[0.04] border border-white/[0.08] text-white placeholder:text-zinc-600 focus:outline-none focus:border-[#8B5CF6]/50 transition-all py-3 px-4 text-[15px] rounded-xl"
              required
            />
          </div>

          {/* Password */}
          <div>
            <label
              htmlFor="password"
              className="block text-[13px] text-zinc-500 mb-2"
            >
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              data-testid="login-password-input"
              placeholder="Enter password"
              className="w-full bg-white/[0.04] border border-white/[0.08] text-white placeholder:text-zinc-600 focus:outline-none focus:border-[#8B5CF6]/50 transition-all py-3 px-4 text-[15px] rounded-xl"
              required
            />
          </div>

          {/* Submit */}
          <button
            type="submit"
            data-testid="login-submit-btn"
            className="mt-2 w-full py-3.5 bg-[#8B5CF6] text-white text-[14px] font-medium rounded-full hover:bg-[#A78BFA] transition-all duration-300 shadow-[0_0_20px_rgba(139,92,246,0.25)] hover:shadow-[0_0_35px_rgba(139,92,246,0.4)]"
          >
            Sign in
          </button>
        </form>

        <p className="mt-6 text-[12px] text-zinc-600 text-center">
          Demo: use admin@nova.ai to access Studio
        </p>
      </div>
    </div>
  );
}
