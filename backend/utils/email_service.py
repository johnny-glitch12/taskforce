"""
email_service — Transactional emails via Resend.

Hooks into:
  - Registration         → welcome + 50-cr bonus reminder
  - Waitlist signup      → confirmation
  - Password reset       → secure link
  - Bounty awarded       → winner notification
  - Bounty submission    → poster notification
  - Tier upgrade         → renewal confirmation

Design rules:
  • Email failures NEVER block the user action — every send is fire-and-forget
    behind a try/except. The auth flow still succeeds if Resend is down.
  • API key + domain come from .env. Set RESEND_API_KEY="" in dev to disable.
  • Inline-CSS dark theme matching the Task Force AI brand.
  • Domain `taskforce.run` must be verified in the Resend dashboard for
    deliverability — SPF + DKIM + (optional) DMARC DNS records.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("email_service")

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
EMAIL_FROM = os.environ.get("EMAIL_FROM", "Task Force AI <noreply@taskforce.run>")
PLATFORM_URL = os.environ.get("PLATFORM_URL", "https://taskforce.run")
EMAIL_ENABLED = bool(RESEND_API_KEY)

# Configure Resend lazily — the module imports cleanly even when not installed.
_resend = None
if EMAIL_ENABLED:
    try:
        import resend  # type: ignore
        resend.api_key = RESEND_API_KEY
        _resend = resend
    except Exception as e:
        logger.warning(f"[email] resend SDK not available — emails disabled: {e}")
        EMAIL_ENABLED = False


async def send_email(to: str, subject: str, html: str) -> dict:
    """Send a transactional email via Resend.

    Returns {"success": True, "id": "..."} on send, or {"success": False, "error": "..."}.
    Never raises — caller can ignore the return value if they don't care.
    """
    if not EMAIL_ENABLED or not _resend:
        logger.info(f"[email:disabled] would send to {to}: '{subject}'")
        return {"success": False, "error": "EMAIL_DISABLED"}
    if not to or "@" not in to:
        return {"success": False, "error": "INVALID_RECIPIENT"}

    try:
        # resend.Emails.send is synchronous — wrap in to_thread so we don't
        # block the FastAPI event loop on the network round-trip.
        import asyncio
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: _resend.Emails.send({
                "from": EMAIL_FROM,
                "to": [to],
                "subject": subject,
                "html": html,
            }),
        )
        return {"success": True, "id": (result or {}).get("id")}
    except Exception as e:
        logger.warning(f"[email] failed to send to {to}: {e}")
        return {"success": False, "error": str(e)[:200]}


# ─── Shared wrapper ────────────────────────────────────
def _wrap(content: str, year: int, platform_url: str) -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0; padding:0; background-color:#0a0a0f; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#0a0a0f; padding:40px 20px;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background-color:#12121a; border-radius:12px; border:1px solid #1e1e2e; overflow:hidden; max-width:600px;">
        <tr><td style="padding:32px 40px 24px; border-bottom:1px solid #1e1e2e;">
          <span style="font-size:20px; font-weight:700; color:#00e5ff; letter-spacing:1px; font-family:'JetBrains Mono', ui-monospace, monospace;">TASK FORCE AI</span>
        </td></tr>
        <tr><td style="padding:40px;">
          {content}
        </td></tr>
        <tr><td style="padding:24px 40px; border-top:1px solid #1e1e2e; text-align:center;">
          <p style="margin:0; font-size:12px; color:#555;">
            &copy; {year} Task Force AI &middot; <a href="{platform_url}" style="color:#00e5ff; text-decoration:none;">taskforce.run</a>
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


def _btn(href: str, label: str) -> str:
    return (f'<a href="{href}" style="display:inline-block; padding:14px 32px; '
            f'background-color:#00e5ff; color:#000; font-size:14px; font-weight:700; '
            f'text-decoration:none; border-radius:8px; letter-spacing:0.5px;">{label}</a>')


# ─── Public send functions ─────────────────────────────
async def send_welcome_email(email: str, username: str) -> dict:
    """After successful registration."""
    year = datetime.now(timezone.utc).year
    safe_name = (username or "operative").strip()[:120]
    content = f"""
<h1 style="margin:0 0 16px; font-size:24px; color:#ffffff;">Welcome aboard, {safe_name}</h1>
<p style="margin:0 0 24px; font-size:16px; color:#a0a0b0; line-height:1.6;">
  Your account is live and loaded with <strong style="color:#00e5ff;">50 free credits</strong> to get started.
</p>
<p style="margin:0 0 12px; font-size:16px; color:#a0a0b0; line-height:1.6;">Here&rsquo;s what you can do right now:</p>
<table cellpadding="0" cellspacing="0" style="margin:0 0 24px;">
  <tr><td style="padding:6px 0; color:#a0a0b0; font-size:14px;">&#x2022;&nbsp; <strong style="color:#fff;">Build an agent</strong> &mdash; describe what you want, AI writes the code</td></tr>
  <tr><td style="padding:6px 0; color:#a0a0b0; font-size:14px;">&#x2022;&nbsp; <strong style="color:#fff;">Browse The Exchange</strong> &mdash; deploy agents built by the community</td></tr>
  <tr><td style="padding:6px 0; color:#a0a0b0; font-size:14px;">&#x2022;&nbsp; <strong style="color:#fff;">Post a bounty</strong> &mdash; request a custom agent and pay the best builder</td></tr>
</table>
{_btn(f"{PLATFORM_URL}/armory", "START BUILDING")}"""
    html = _wrap(content, year, PLATFORM_URL)
    return await send_email(email, "Welcome to Task Force AI — 50 credits on us", html)


async def send_waitlist_email(email: str) -> dict:
    """After waitlist signup."""
    year = datetime.now(timezone.utc).year
    safe_email = (email or "").strip()[:200]
    content = f"""
<h1 style="margin:0 0 16px; font-size:24px; color:#ffffff;">You&rsquo;re on the list</h1>
<p style="margin:0 0 24px; font-size:16px; color:#a0a0b0; line-height:1.6;">
  We&rsquo;ve saved your spot. When Task Force AI opens up, you&rsquo;ll be among the first to know.
</p>
<p style="margin:0 0 8px; font-size:14px; color:#555;">Signed up with: <strong style="color:#a0a0b0;">{safe_email}</strong></p>
"""
    html = _wrap(content, year, PLATFORM_URL)
    return await send_email(email, "You're on the Task Force AI waitlist", html)


async def send_password_reset_email(email: str, username: Optional[str], reset_token: str) -> dict:
    """Reset link email."""
    year = datetime.now(timezone.utc).year
    name = (username or "operative").strip()[:120]
    reset_url = f"{PLATFORM_URL}/auth/reset-password?token={reset_token}"
    content = f"""
<h1 style="margin:0 0 16px; font-size:24px; color:#ffffff;">Reset your password</h1>
<p style="margin:0 0 24px; font-size:16px; color:#a0a0b0; line-height:1.6;">
  Hey {name}, we got a request to reset your password. Click below to set a new one. This link expires in 1 hour.
</p>
{_btn(reset_url, "RESET PASSWORD")}
<p style="margin:24px 0 0; font-size:13px; color:#555;">If you didn&rsquo;t request this, just ignore this email. Your password won&rsquo;t change.</p>
"""
    html = _wrap(content, year, PLATFORM_URL)
    return await send_email(email, "Reset your Task Force AI password", html)


async def send_bounty_awarded_email(email: str, username: str, bounty_title: str, reward_display: str, bounty_id: Optional[str] = None) -> dict:
    """Bounty winner notification."""
    year = datetime.now(timezone.utc).year
    safe_name = (username or "operative").strip()[:120]
    safe_title = (bounty_title or "").strip()[:200]
    link = f"{PLATFORM_URL}/bounties/{bounty_id}" if bounty_id else f"{PLATFORM_URL}/bounties"
    content = f"""
<h1 style="margin:0 0 16px; font-size:24px; color:#ffffff;">You won a bounty!</h1>
<p style="margin:0 0 24px; font-size:16px; color:#a0a0b0; line-height:1.6;">
  Congrats {safe_name} &mdash; your submission for <strong style="color:#fff;">{safe_title}</strong> was selected as the winner.
</p>
<p style="margin:0 0 24px; font-size:20px; color:#00e5ff; font-weight:700;">{reward_display}</p>
{_btn(link, "VIEW BOUNTY")}
"""
    html = _wrap(content, year, PLATFORM_URL)
    return await send_email(email, f"You won the bounty: {safe_title}", html)


async def send_submission_received_email(email: str, username: str, bounty_title: str, bounty_id: Optional[str] = None) -> dict:
    """Poster notification when a new submission arrives."""
    year = datetime.now(timezone.utc).year
    safe_name = (username or "operative").strip()[:120]
    safe_title = (bounty_title or "").strip()[:200]
    link = f"{PLATFORM_URL}/bounties/{bounty_id}" if bounty_id else f"{PLATFORM_URL}/bounties"
    content = f"""
<h1 style="margin:0 0 16px; font-size:24px; color:#ffffff;">New submission on your bounty</h1>
<p style="margin:0 0 24px; font-size:16px; color:#a0a0b0; line-height:1.6;">
  Hey {safe_name}, someone just submitted a solution for <strong style="color:#fff;">{safe_title}</strong>. Head over to review it.
</p>
{_btn(link, "REVIEW SUBMISSION")}
"""
    html = _wrap(content, year, PLATFORM_URL)
    return await send_email(email, f"New submission on your bounty: {safe_title}", html)


async def send_tier_upgrade_email(email: str, username: str, tier: str, monthly_credits: int) -> dict:
    """Subscription tier upgrade confirmation (Stripe webhook)."""
    year = datetime.now(timezone.utc).year
    safe_name = (username or "operative").strip()[:120]
    tier_label = (tier or "").capitalize() or "Unknown"
    content = f"""
<h1 style="margin:0 0 16px; font-size:24px; color:#ffffff;">You&rsquo;re now {tier_label}</h1>
<p style="margin:0 0 24px; font-size:16px; color:#a0a0b0; line-height:1.6;">
  {safe_name}, your plan has been upgraded. You now get <strong style="color:#00e5ff;">{monthly_credits} credits/month</strong> that reset every billing cycle.
</p>
{_btn(f"{PLATFORM_URL}/credits", "VIEW YOUR CREDITS")}
"""
    html = _wrap(content, year, PLATFORM_URL)
    return await send_email(email, f"Welcome to {tier_label} — your credits are ready", html)


__all__ = [
    "send_email",
    "send_welcome_email",
    "send_waitlist_email",
    "send_password_reset_email",
    "send_bounty_awarded_email",
    "send_submission_received_email",
    "send_tier_upgrade_email",
    "EMAIL_ENABLED",
]
