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
    <div className="min-h-[calc(100vh-64px)] flex items-center justify-center px-6">
      <div
        data-testid="login-card"
        className="w-full max-w-md bg-zinc-900 border border-zinc-800 p-8 md:p-10 animate-fade-in-up"
        style={{ animationFillMode: "forwards" }}
      >
        {/* Header */}
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 bg-zinc-800 flex items-center justify-center">
            <Lock size={18} className="text-[#00E5FF]" />
          </div>
          <div>
            <h2
              className="text-xl font-bold text-white tracking-tight"
              style={{ fontFamily: "'Outfit', sans-serif" }}
            >
              Sign In
            </h2>
            <p className="text-xs font-mono uppercase tracking-[0.15em] text-zinc-500">
              Private Beta Access
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-6">
          {/* Email */}
          <div>
            <label
              htmlFor="email"
              className="block text-xs font-mono uppercase tracking-[0.2em] text-zinc-500 mb-2"
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
              className="w-full bg-transparent border-b-2 border-zinc-700 text-white placeholder:text-zinc-600 focus:outline-none focus:border-[#00E5FF] transition-colors py-3 text-base"
              required
            />
          </div>

          {/* Password */}
          <div>
            <label
              htmlFor="password"
              className="block text-xs font-mono uppercase tracking-[0.2em] text-zinc-500 mb-2"
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
              className="w-full bg-transparent border-b-2 border-zinc-700 text-white placeholder:text-zinc-600 focus:outline-none focus:border-[#00E5FF] transition-colors py-3 text-base"
              required
            />
          </div>

          {/* Submit */}
          <button
            type="submit"
            data-testid="login-submit-btn"
            className="mt-4 w-full py-4 bg-[#00E5FF] text-black text-sm font-semibold uppercase tracking-wider hover:bg-[#B900FF] hover:text-white transition-all duration-300 shadow-[0_0_15px_rgba(0,229,255,0.2)] hover:shadow-[0_0_20px_rgba(185,0,255,0.5)]"
          >
            Sign In
          </button>
        </form>

        <p className="mt-6 text-xs text-zinc-500 text-center font-mono">
          Demo: use admin@nova.ai to access Studio
        </p>
      </div>
    </div>
  );
}
