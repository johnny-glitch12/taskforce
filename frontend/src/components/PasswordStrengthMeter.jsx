/**
 * PasswordStrengthMeter — bar + GitHub-style checklist.
 *
 * Mirrors backend lib/auth_validators.py:check_password() scoring so the user
 * sees the same outcome locally as the server would compute. Backend is still
 * the source of truth — this is purely for UX.
 *
 * Score 0..4 maps to: Weak (red) / Fair (orange) / Good (yellow) / Strong (green).
 *
 * Props:
 *   - value       (string)   current password input
 *   - username    (string)   blocks "password == username"
 *   - email       (string)   blocks "password == email"
 *   - testidPrefix (string)  for data-testid prefixing (e.g. "signup-pwd")
 */
import { CheckCircle2, Circle } from "lucide-react";

const SPECIAL_RE = /[!@#$%^&*()_+\-=\[\]{}|;:',.<>?/\\]/;

export function scorePassword(pwd, username = "", email = "") {
  const p = pwd || "";
  const rules = {
    length: p.length >= 8,
    uppercase: /[A-Z]/.test(p),
    lowercase: /[a-z]/.test(p),
    number: /[0-9]/.test(p),
    special: SPECIAL_RE.test(p),
    max_length: p.length <= 128,
    no_whitespace_trim: p === p.trim(),
    not_username_or_email:
      p.toLowerCase() !== (username || "").toLowerCase() &&
      p.toLowerCase() !== (email || "").toLowerCase() &&
      p.toLowerCase() !== (email || "").split("@")[0].toLowerCase(),
  };

  const charTypes = [rules.uppercase, rules.lowercase, rules.number, rules.special].filter(Boolean).length;
  let score = 0;
  if (rules.length) {
    if (charTypes >= 4 && p.length >= 12) score = 4;
    else if (charTypes >= 3) score = 3;
    else if (charTypes >= 2) score = 2;
    else score = 1;
  }
  const ok = Object.values(rules).every(Boolean);
  return { ok, score, rules };
}

const LEVELS = [
  { label: "—", barClass: "bg-zinc-800", textClass: "text-zinc-500", pct: 0 },
  { label: "Weak", barClass: "bg-rose-500", textClass: "text-rose-400", pct: 25 },
  { label: "Fair", barClass: "bg-orange-400", textClass: "text-orange-300", pct: 50 },
  { label: "Good", barClass: "bg-yellow-400", textClass: "text-yellow-300", pct: 75 },
  { label: "Strong", barClass: "bg-emerald-400", textClass: "text-emerald-300", pct: 100 },
];

export default function PasswordStrengthMeter({ value, username = "", email = "", testidPrefix = "password" }) {
  const { score, rules } = scorePassword(value, username, email);
  const level = LEVELS[score] || LEVELS[0];
  // Don't show anything until the user has typed at least one char.
  if (!value) return null;

  return (
    <div className="mt-2 space-y-2" data-testid={`${testidPrefix}-meter`}>
      {/* Bar */}
      <div className="flex items-center gap-2">
        <div className="flex-1 h-1.5 rounded-full bg-zinc-900 overflow-hidden">
          <div
            data-testid={`${testidPrefix}-meter-bar`}
            data-score={score}
            className={`h-full ${level.barClass} transition-all duration-300`}
            style={{ width: `${level.pct}%`, boxShadow: `0 0 8px ${level.barClass.includes("rose") ? "rgba(244,63,94,0.4)" : level.barClass.includes("orange") ? "rgba(251,146,60,0.4)" : level.barClass.includes("yellow") ? "rgba(250,204,21,0.4)" : level.barClass.includes("emerald") ? "rgba(52,211,153,0.4)" : "transparent"}` }}
          />
        </div>
        <span
          data-testid={`${testidPrefix}-meter-label`}
          className={`text-[10px] font-mono uppercase tracking-[0.15em] font-bold w-12 text-right ${level.textClass}`}
        >
          {level.label}
        </span>
      </div>

      {/* Checklist */}
      <ul className="grid grid-cols-1 sm:grid-cols-2 gap-x-3 gap-y-0.5 text-[11px]">
        <Item ok={rules.length} testid={`${testidPrefix}-rule-length`}>At least 8 characters</Item>
        <Item ok={rules.uppercase} testid={`${testidPrefix}-rule-upper`}>Uppercase letter</Item>
        <Item ok={rules.lowercase} testid={`${testidPrefix}-rule-lower`}>Lowercase letter</Item>
        <Item ok={rules.number} testid={`${testidPrefix}-rule-number`}>Number</Item>
        <Item ok={rules.special} testid={`${testidPrefix}-rule-special`}>Special character</Item>
        {!rules.not_username_or_email && (
          <Item ok={false} testid={`${testidPrefix}-rule-distinct`}>
            Different from your username/email
          </Item>
        )}
      </ul>
    </div>
  );
}

function Item({ ok, testid, children }) {
  return (
    <li
      data-testid={testid}
      data-pass={ok || undefined}
      className={`flex items-center gap-1.5 ${ok ? "text-emerald-400" : "text-zinc-500"}`}
    >
      {ok ? <CheckCircle2 size={11} /> : <Circle size={11} />}
      <span>{children}</span>
    </li>
  );
}
