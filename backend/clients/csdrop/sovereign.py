import asyncio
import random
import sqlite3
import json
import os
import time
import sys
import requests
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from playwright_stealth import stealth_async

# ─── Absolute Paths ───
BOT_DIR = Path(__file__).resolve().parent
SCREENSHOT_DIR = Path("/app/backend/static")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOT_PATH = SCREENSHOT_DIR / "live_stream.jpg"
QR_SCREENSHOT_PATH = SCREENSHOT_DIR / "qr_sync.jpg"
SESSION_FILE = BOT_DIR / "discord_session.json"
DB_FILE = BOT_DIR / "omni_viper_v8.db"

LOGIN_TIMEOUT = 120  # 2 minutes

# ─── Stealth Browser Config ───
STEALTH_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
STEALTH_VIEWPORT = {"width": 1920, "height": 1080}
DEBUG_SCREENSHOT_PATH = SCREENSHOT_DIR / "debug_render.jpg"
CYCLE_TIMEOUT_PATH = SCREENSHOT_DIR / "cycle_timeout_debug.jpg"
BOT_SIGNAL_FILE = BOT_DIR / "bot_signal.txt"


ERROR_SCREENSHOT_PATH = SCREENSHOT_DIR / "error_last.jpg"


async def _capture_error(page, context_msg=""):
    """Save an error screenshot for debugging."""
    try:
        await page.screenshot(path=str(ERROR_SCREENSHOT_PATH), type="jpeg", quality=70)
        print(f"[ERROR] Screenshot saved to {ERROR_SCREENSHOT_PATH} ({context_msg})", flush=True)
    except Exception:
        pass


async def _capture_feed(page):
    """Save a screenshot for the Live Satellite Feed on the dashboard."""
    try:
        await page.screenshot(path=str(SCREENSHOT_PATH), type="jpeg", quality=50)
        print("[SYSTEM] Screenshot captured for Dashboard.")
    except Exception:
        pass


# ==========================================
# V. LOGIN / SESSION SYNC MODE
# ==========================================
async def login_mode():
    """
    Opens Discord login page, captures QR screenshots every 2s,
    waits for a successful scan, saves the session, and exits.
    """
    print("[LOGIN] Session Sync Mode activated.", flush=True)
    print(f"[LOGIN] Timeout: {LOGIN_TIMEOUT}s. Scan the QR code from your Discord mobile app.", flush=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        page = await context.new_page()
        await stealth_async(page)

        print("[LOGIN] Navigating to Discord login...", flush=True)
        try:
            await page.goto("https://discord.com/login", wait_until="networkidle", timeout=45000)
            print("[LOGIN] Discord login page loaded.", flush=True)
            # Give the QR code time to render
            await asyncio.sleep(3)
            # Capture initial screenshot immediately
            await page.screenshot(path=str(QR_SCREENSHOT_PATH), type="jpeg", quality=70)
            print("[LOGIN] Initial QR screenshot saved.", flush=True)
        except Exception as e:
            print(f"[LOGIN] Failed to load Discord login: {e}", flush=True)
            # Still try to capture whatever loaded
            try:
                await page.screenshot(path=str(QR_SCREENSHOT_PATH), type="jpeg", quality=70)
                print("[LOGIN] Captured partial page screenshot.", flush=True)
            except Exception:
                pass
            await browser.close()
            return False

        start_time = time.time()
        success = False

        while (time.time() - start_time) < LOGIN_TIMEOUT:
            # Capture QR code screenshot
            try:
                await page.screenshot(path=str(QR_SCREENSHOT_PATH), type="jpeg", quality=70)
                elapsed = int(time.time() - start_time)
                remaining = LOGIN_TIMEOUT - elapsed
                print(f"[LOGIN] QR captured. Waiting for scan... ({remaining}s remaining)", flush=True)
            except Exception:
                pass

            # Check if URL changed to channels (successful login)
            current_url = page.url
            if "/channels" in current_url:
                print("[LOGIN] SUCCESS! Discord login detected.", flush=True)
                success = True
                break

            await asyncio.sleep(2)

        if success:
            # Save the authenticated session
            try:
                await context.storage_state(path=str(SESSION_FILE))
                print(f"[LOGIN] Session saved to {SESSION_FILE}", flush=True)
                # Final screenshot showing logged-in state
                await page.screenshot(path=str(QR_SCREENSHOT_PATH), type="jpeg", quality=70)
            except Exception as e:
                print(f"[LOGIN] Failed to save session: {e}", flush=True)
                success = False
        else:
            print("[LOGIN] TIMEOUT. No scan detected within 2 minutes.", flush=True)
            # Clean up the QR screenshot
            try:
                QR_SCREENSHOT_PATH.unlink(missing_ok=True)
            except Exception:
                pass

        await browser.close()
        status = "success" if success else "timeout"
        print(f"[LOGIN] Exit status: {status}", flush=True)
        return success


# ==========================================
# VI. MANUAL LOGIN MODE (Email/Password + 2FA)
# ==========================================
MANUAL_TIMEOUT = 180  # 3 minutes total
SIGNAL_2FA_FILE = BOT_DIR / "2fa_signal.txt"
MANUAL_CREDS_FILE = BOT_DIR / "manual_creds.json"


async def manual_login_mode():
    """
    Reads email/password from manual_creds.json, types them into Discord,
    handles 2FA challenges by waiting for 2fa_signal.txt, saves session.
    """
    print("[MANUAL] Manual Credential Bridge activated.", flush=True)

    # Read credentials
    if not MANUAL_CREDS_FILE.exists():
        print("[MANUAL] FATAL: manual_creds.json not found.", flush=True)
        return False

    try:
        creds = json.loads(MANUAL_CREDS_FILE.read_text())
        email = creds["email"]
        password = creds["password"]
        print(f"[MANUAL] Credentials loaded for: {email}", flush=True)
    except Exception as e:
        print(f"[MANUAL] FATAL: Failed to read credentials: {e}", flush=True)
        return False
    finally:
        # Delete creds file immediately for security
        try:
            MANUAL_CREDS_FILE.unlink(missing_ok=True)
        except Exception:
            pass

    # Clean up any old signal file
    try:
        SIGNAL_2FA_FILE.unlink(missing_ok=True)
    except Exception:
        pass

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport=STEALTH_VIEWPORT,
            user_agent=STEALTH_UA,
        )
        page = await context.new_page()
        await stealth_async(page)

        # Navigate to Discord login
        print("[MANUAL] Navigating to Discord login...", flush=True)
        try:
            await page.goto("https://discord.com/login", wait_until="networkidle", timeout=45000)
            await asyncio.sleep(3)
            await page.screenshot(path=str(QR_SCREENSHOT_PATH), type="jpeg", quality=70)
            print("[MANUAL] Login page loaded.", flush=True)
        except Exception as e:
            print(f"[MANUAL] Failed to load login page: {e}", flush=True)
            await browser.close()
            return False

        # Type email
        try:
            print("[MANUAL] Entering email...", flush=True)
            email_input = await page.wait_for_selector('input[name="email"]', timeout=10000)
            await email_input.click()
            await asyncio.sleep(0.5)
            await email_input.fill("")
            await email_input.type(email, delay=random.randint(40, 80))
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"[MANUAL] Failed to enter email: {e}", flush=True)
            await page.screenshot(path=str(ERROR_SCREENSHOT_PATH), type="jpeg", quality=70)
            await browser.close()
            return False

        # Type password
        try:
            print("[MANUAL] Entering password...", flush=True)
            pw_input = await page.wait_for_selector('input[name="password"]', timeout=10000)
            await pw_input.click()
            await asyncio.sleep(0.5)
            await pw_input.type(password, delay=random.randint(40, 80))
            await asyncio.sleep(1)
        except Exception as e:
            print(f"[MANUAL] Failed to enter password: {e}", flush=True)
            await page.screenshot(path=str(ERROR_SCREENSHOT_PATH), type="jpeg", quality=70)
            await browser.close()
            return False

        # Submit login
        print("[MANUAL] Submitting login...", flush=True)
        await page.keyboard.press("Enter")
        await asyncio.sleep(5)
        await page.screenshot(path=str(QR_SCREENSHOT_PATH), type="jpeg", quality=70)

        # Check result — success, error, or 2FA challenge
        start_time = time.time()
        success = False

        while (time.time() - start_time) < MANUAL_TIMEOUT:
            current_url = page.url

            # Check: Login succeeded (redirected to channels)
            if "/channels" in current_url:
                print("[MANUAL] SUCCESS! Login detected.", flush=True)
                success = True
                break

            # Check: 2FA / MFA challenge screen
            page_content = await page.content()
            needs_2fa = False

            # Discord 2FA indicators
            mfa_selectors = [
                'input[placeholder*="6-digit"]',
                'input[placeholder*="authentication"]',
                'input[aria-label*="code"]',
                'input[autocomplete="one-time-code"]',
            ]
            for selector in mfa_selectors:
                try:
                    elem = await page.query_selector(selector)
                    if elem:
                        needs_2fa = True
                        break
                except Exception:
                    pass

            # Also check text content for 2FA/email verification prompts
            if not needs_2fa:
                for phrase in ["Two-Factor", "2FA", "Enter the code", "Check your email", "verification code", "Verify your identity"]:
                    if phrase.lower() in page_content.lower():
                        needs_2fa = True
                        break

            if needs_2fa:
                print("[MANUAL] 2FA_REQUIRED — Waiting for verification code...", flush=True)
                await page.screenshot(path=str(QR_SCREENSHOT_PATH), type="jpeg", quality=70)

                # Enter the 2FA waiting loop
                code_entered = False
                while (time.time() - start_time) < MANUAL_TIMEOUT:
                    # Check if signal file appeared
                    if SIGNAL_2FA_FILE.exists():
                        try:
                            code = SIGNAL_2FA_FILE.read_text().strip()
                            SIGNAL_2FA_FILE.unlink(missing_ok=True)
                            print(f"[MANUAL] 2FA code received: {code}", flush=True)

                            # Find the 2FA input and type the code
                            typed = False
                            for selector in mfa_selectors:
                                try:
                                    code_input = await page.wait_for_selector(selector, timeout=5000)
                                    if code_input:
                                        await code_input.click()
                                        await asyncio.sleep(0.5)
                                        await code_input.fill("")
                                        await code_input.type(code, delay=random.randint(60, 120))
                                        typed = True
                                        break
                                except Exception:
                                    continue

                            if not typed:
                                # Fallback: just type into whatever is focused
                                print("[MANUAL] Using keyboard fallback for 2FA input...", flush=True)
                                await page.keyboard.type(code, delay=random.randint(60, 120))

                            await asyncio.sleep(1)
                            await page.keyboard.press("Enter")
                            print("[MANUAL] 2FA code submitted. Waiting for result...", flush=True)
                            await asyncio.sleep(5)
                            await page.screenshot(path=str(QR_SCREENSHOT_PATH), type="jpeg", quality=70)
                            code_entered = True
                            break
                        except Exception as e:
                            print(f"[MANUAL] Error entering 2FA code: {e}", flush=True)
                            await page.screenshot(path=str(ERROR_SCREENSHOT_PATH), type="jpeg", quality=70)
                            break

                    elapsed = int(time.time() - start_time)
                    remaining = MANUAL_TIMEOUT - elapsed
                    print(f"[MANUAL] Waiting for 2FA code... ({remaining}s remaining)", flush=True)
                    await page.screenshot(path=str(QR_SCREENSHOT_PATH), type="jpeg", quality=70)
                    await asyncio.sleep(2)

                if not code_entered:
                    print("[MANUAL] TIMEOUT waiting for 2FA code.", flush=True)
                    break

                # After 2FA, continue checking for redirect
                continue

            # Check: Login error (wrong password etc)
            for err_text in ["Login or password is invalid", "INVALID_LOGIN", "ACCOUNT_LOGIN_VERIFICATION_EMAIL"]:
                if err_text.lower() in page_content.lower():
                    print(f"[MANUAL] LOGIN FAILED — Discord says: {err_text}", flush=True)
                    await page.screenshot(path=str(ERROR_SCREENSHOT_PATH), type="jpeg", quality=70)
                    await browser.close()
                    return False

            elapsed = int(time.time() - start_time)
            remaining = MANUAL_TIMEOUT - elapsed
            print(f"[MANUAL] Waiting for login result... ({remaining}s remaining)", flush=True)
            await page.screenshot(path=str(QR_SCREENSHOT_PATH), type="jpeg", quality=70)
            await asyncio.sleep(2)

        if success:
            try:
                await context.storage_state(path=str(SESSION_FILE))
                print(f"[MANUAL] Session saved to {SESSION_FILE}", flush=True)
                await page.screenshot(path=str(QR_SCREENSHOT_PATH), type="jpeg", quality=70)
            except Exception as e:
                print(f"[MANUAL] Failed to save session: {e}", flush=True)
                success = False
        else:
            print("[MANUAL] TIMEOUT. Login did not complete.", flush=True)

        # Cleanup
        try:
            SIGNAL_2FA_FILE.unlink(missing_ok=True)
        except Exception:
            pass

        await browser.close()
        status = "success" if success else "timeout"
        print(f"[MANUAL] Exit status: {status}", flush=True)
        return success

# ==========================================
# I. CONFIGURATION (Keep your site/links here)
# ==========================================
CONFIG = {
    "PROXY": "http://spzi6md7ie:4u_eyh8sZM3KElhty2@gate.decodo.com:10010",
    "DB_PATH": str(DB_FILE),
    "SESSION_FILE": str(SESSION_FILE),
    "LINKS": {
        "SITE": "csdrop.com",
        "PROMO": "https://csdrop.com/r/YOURCODE",
        "X": "https://x.com/csdropcom"
    }
}

PROMO_TEMPLATES = [
    "bet, check {site} - use {link}", "safe, hit {site} with {link}", "legend, {site} is fire. {link}",
    "no worries, check the link in my bio real quick", "all good, check my profile bio for the link",
    "sweet, check {site} at {link}", "easy, {site} is paying out. {link}", "check my bio for the code and link",
    "yo, check {link} for {site}", "bet, {site} is the one. {link}", "check my profile, link is in the bio",
    "safe, use {link} for {site}", "legend, use {link}", "it is on my bio, check it out",
    "check the bio link for the site", "it is {site}, use {link}", "use {link} for the bonus",
    "check my bio for the site link", "safe, {site} is the move. {link}", "bet, check bio",
    "check the link on my profile", "i put the link in my bio", "check my bio for the drop",
    "use {link} on {site}", "safe, hit the link in my bio", "bet, use {link} for the skins",
    "check my bio real quick", "link is in the bio on my profile", "use code in my bio",
    "safe, check {site} {link}", "legend, use {link} for the site", "check bio for the link",
    "it is in my bio", "check my profile bio", "bet, link is in bio", "safe, check {link}",
    "use {link} for {site} rewards", "check my bio for the rewards", "link in bio bro",
    "check bio link", "safe, check my bio", "bet, use {link} for {site}", "check bio for site",
    "it is in the bio", "check profile bio", "use {link} for site", "link in bio",
    "check my bio for the site", "safe, link in bio", "bet, check my bio for {site}"
]

HOOK_TEMPLATES = ["yo {username}, you got a sec? i need a quick favor", "hey {username}, can i ask you something real quick?"]

# ==========================================
# II. HARDENED STEALTH MODULES
# ==========================================

async def human_lurk(page):
    try:
        print("    [*] Lurking (Session Warming)...", flush=True)
        servers = await page.query_selector_all('div[role="treeitem"]')
        if servers:
            await random.choice(servers).click()
            await asyncio.sleep(random.randint(5, 10))
        await page.click('a[aria-label="Direct Messages"]', timeout=5000)
    except Exception:
        pass

async def human_search_and_click(page, username):
    """Uses Ctrl+K and '@' prefix with jitter to bypass Captchas."""
    try:
        print(f"    [*] Triggering Stealth Search for @{username}...", flush=True)
        await asyncio.sleep(random.uniform(1.5, 3.5))
        await page.keyboard.press("Control+k")
        await asyncio.sleep(random.uniform(1.5, 2.5))
        search_input = await page.wait_for_selector('[placeholder="Where would you like to go?"]', timeout=10000)
        await search_input.type("@", delay=random.randint(200, 450))
        await asyncio.sleep(random.uniform(0.8, 1.5))
        await search_input.type(username, delay=random.randint(110, 230))
        await asyncio.sleep(random.uniform(4, 6))  # Filter time
        await page.keyboard.press("Enter")
        await asyncio.sleep(random.randint(8, 12))

        # Verify we actually landed on a DM page
        current_url = page.url
        if "/channels/" not in current_url:
            print(f"    [WARN] Search for @{username} did not land on a DM page (URL: {current_url})", flush=True)
            await _capture_error(page, f"search_no_dm_{username}")
            return False

        return True
    except Exception as e:
        print(f"    [ERROR] Search failed for @{username}: {e}", flush=True)
        await _capture_error(page, f"search_fail_{username}")
        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass
        return False


async def _verify_message_sent(page, timeout=10):
    """Verify a message was actually sent by checking the textbox is empty."""
    try:
        start = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start) < timeout:
            textbox = await page.query_selector('[role="textbox"], [aria-label*="Message"]')
            if textbox:
                text_content = await textbox.text_content()
                if not text_content or text_content.strip() == "":
                    return True
            await asyncio.sleep(1)
        return False
    except Exception:
        return False


async def _dismiss_modals(page):
    """Close any open user profile popups or overlays that could block the next action."""
    try:
        await page.keyboard.press("Escape")
        await asyncio.sleep(0.5)
        await page.keyboard.press("Escape")
        await asyncio.sleep(0.3)
    except Exception:
        pass

# ==========================================
# III. THE INFINITE PREDATOR ENGINE
# ==========================================
class PredatorEngine:
    def __init__(self, page, db_conn):
        self.page = page
        self.db = db_conn
        self.cursor = db_conn.cursor()

    async def hammer_check(self):
        """PHASE 1: THE DEEP SCAN. Checks all hooked users for replies."""
        self.cursor.execute("SELECT user_id, username FROM targets WHERE status = 'hooked'")
        targets = self.cursor.fetchall()
        if not targets:
            return

        print(f"\n--- [ PHASE 1: THE HAMMER ] (Checking {len(targets)} replies) ---", flush=True)
        for u_id, u_name in targets:
            try:
                print(f"    [*] Scanning @{u_name}...", flush=True)
                await self.page.goto("https://discord.com/channels/@me", wait_until="networkidle", timeout=45000)
                await asyncio.sleep(random.uniform(3, 5))
                if not await human_search_and_click(self.page, u_name):
                    continue

                await asyncio.sleep(random.randint(5, 8))
                msgs = await self.page.query_selector_all('li[class*="message_"]')
                content = await self.page.content()
                await _capture_feed(self.page)

                # Logic: If total messages > 1 and we haven't dropped our link yet
                if len(msgs) >= 2 and CONFIG["LINKS"]["SITE"] not in content:
                    print(f"    [!] REAL REPLY confirmed from @{u_name}!", flush=True)
                    msg = random.choice(PROMO_TEMPLATES).format(site=CONFIG["LINKS"]["SITE"], link=CONFIG["LINKS"]["PROMO"])

                    # Click textbox and type with human delay
                    try:
                        textbox = self.page.locator('[role="textbox"], [aria-label*="Message"]').first
                        await textbox.wait_for(timeout=10000)
                    except Exception:
                        print(f"    [ERROR] Selector Timeout — textbox not found for @{u_name}", flush=True)
                        await self.page.screenshot(path=str(DEBUG_SCREENSHOT_PATH), type="jpeg", quality=70)
                        print(f"    [DEBUG] Render screenshot saved to {DEBUG_SCREENSHOT_PATH}", flush=True)
                        await _dismiss_modals(self.page)
                        continue
                    await textbox.click()
                    await asyncio.sleep(random.uniform(2, 4))
                    await self.page.keyboard.type(msg, delay=random.randint(80, 160))
                    await asyncio.sleep(random.uniform(1, 2))
                    await self.page.keyboard.press("Enter")
                    await asyncio.sleep(2)

                    # Verify the message was sent
                    if await _verify_message_sent(self.page, timeout=10):
                        print(f"    [SUCCESS] Promo delivered to @{u_name}!", flush=True)
                        self.cursor.execute("UPDATE targets SET status = 'completed' WHERE user_id = ?", (u_id,))
                    else:
                        print(f"    [ERROR] Selector Timeout — message may not have sent to @{u_name}", flush=True)
                        await _capture_error(self.page, f"hammer_verify_{u_name}")

                    self.db.commit()
                    # Human delay between DMs
                    nap = random.uniform(15, 25)
                    print(f"    [*] Cooling down {nap:.0f}s...", flush=True)
                    await asyncio.sleep(nap)
                else:
                    print(f"    [-] No actionable reply from @{u_name}.", flush=True)

            except Exception as e:
                print(f"    [ERROR] Hammer failed on @{u_name}: {e}", flush=True)
                await _capture_error(self.page, f"hammer_{u_name}")
                await _dismiss_modals(self.page)
                continue

    async def hook_strike(self, batch_size=10):
        """PHASE 2: Strikes exactly N new people as requested."""
        # ─── Database Pulse Check ───
        self.cursor.execute("SELECT COUNT(*) FROM targets WHERE status = 'pending'")
        pending_count = self.cursor.fetchone()[0]
        print(f"[DEBUG] Database Found. Pending targets in queue: {pending_count}", flush=True)

        if pending_count == 0:
            print("[!] CRITICAL: Database is empty. Scrape targets before starting strike.", flush=True)
            return

        self.cursor.execute("SELECT user_id, username FROM targets WHERE status = 'pending' LIMIT ?", (batch_size,))
        pending = self.cursor.fetchall()

        print(f"\n--- [ PHASE 2: THE HOOK ] (Striking batch of {len(pending)}) ---", flush=True)
        strikes_sent = 0
        strikes_failed = 0

        for idx, (u_id, u_name) in enumerate(pending):
            try:
                print(f"[*] Striking ({idx+1}/{len(pending)}): @{u_name}", flush=True)
                await self.page.goto("https://discord.com/channels/@me", wait_until="networkidle", timeout=45000)
                await asyncio.sleep(random.uniform(3, 5))

                # Pre-strike wait: ensure sidebar is loaded before searching
                try:
                    await self.page.wait_for_selector('div[class*="searchBar"], a[aria-label="Direct Messages"]', timeout=8000)
                except Exception:
                    print("    [WARN] Sidebar not detected, continuing anyway...", flush=True)

                if not await human_search_and_click(self.page, u_name):
                    print(f"    [ERROR] Could not find @{u_name} in search. Skipping.", flush=True)
                    strikes_failed += 1
                    await _dismiss_modals(self.page)
                    continue

                sent = False
                try:
                    wave_btn = await self.page.wait_for_selector('button:has-text("Wave")', timeout=8000)
                    await wave_btn.click()
                    await asyncio.sleep(2)
                    print("    [+++] WAVE SENT", flush=True)
                    sent = True
                except Exception:
                    # Text Fallback — find the textbox with robust selector
                    try:
                        textbox = self.page.locator('[role="textbox"], [aria-label*="Message"]').first
                        await textbox.wait_for(timeout=10000)
                        await textbox.click()
                        await asyncio.sleep(random.uniform(2, 4))
                        msg = random.choice(HOOK_TEMPLATES).format(username=u_name)
                        await self.page.keyboard.type(msg, delay=random.randint(80, 160))
                        await asyncio.sleep(random.uniform(1, 2))
                        await self.page.keyboard.press("Enter")
                        await asyncio.sleep(2)

                        # Verify the message was actually sent
                        if await _verify_message_sent(self.page, timeout=10):
                            print("    [SUCCESS] TEXT HOOK SENT & VERIFIED", flush=True)
                            sent = True
                        else:
                            print("    [ERROR] Selector Timeout — message box not found or message stuck", flush=True)
                            await _capture_error(self.page, f"hook_verify_{u_name}")
                    except Exception as e:
                        print(f"    [ERROR] Selector Timeout on textbox for @{u_name}: {e}", flush=True)
                        await self.page.screenshot(path=str(DEBUG_SCREENSHOT_PATH), type="jpeg", quality=70)
                        print(f"    [DEBUG] Render screenshot saved to {DEBUG_SCREENSHOT_PATH}", flush=True)
                        await _capture_error(self.page, f"hook_textbox_{u_name}")

                if sent:
                    self.cursor.execute("UPDATE targets SET status = 'hooked' WHERE user_id = ?", (u_id,))
                    strikes_sent += 1
                else:
                    strikes_failed += 1

                self.db.commit()
                # Dismiss any leftover modals before moving on
                await _dismiss_modals(self.page)
                await human_lurk(self.page)
                await _capture_feed(self.page)

                # Human delay between DMs (8-15 seconds)
                nap = random.uniform(8, 15)
                print(f"    [*] Human delay: {nap:.1f}s before next strike...", flush=True)
                await asyncio.sleep(nap)

                # Extra cooldown every 5 strikes
                if (idx + 1) % 5 == 0:
                    big_nap = random.randint(45, 90)
                    print(f"    [*] Batch cooldown: {big_nap}s (anti-detection)...", flush=True)
                    await asyncio.sleep(big_nap)

            except Exception as e:
                print(f"    [ERROR] Strike failed on @{u_name}: {e}", flush=True)
                await _capture_error(self.page, f"strike_{u_name}")
                await _dismiss_modals(self.page)
                strikes_failed += 1
                continue

        print(f"\n[REPORT] Hook Strike Complete: {strikes_sent} sent, {strikes_failed} failed out of {len(pending)}", flush=True)

# ==========================================
# IV. THE INFINITE LOOP MAIN
# ==========================================

# Demo mode: if --demo flag, send one test message then exit
DEMO_TEST_ID = "277083087718973441"  # Hardcoded test Discord user

async def main():
    demo_mode = "--demo" in sys.argv
    promo_link = CONFIG["LINKS"]["PROMO"]
    batch_size = 10

    # Parse CLI args (promo, batch) from server.py launch
    args = [a for a in sys.argv[1:] if a not in ("--login", "--demo")]
    if len(args) >= 1:
        promo_link = args[0]
    if len(args) >= 2:
        try:
            batch_size = int(args[1])
        except ValueError:
            pass

    # ─── Path Verification ───
    print(f"[BOOT] Bot directory: {BOT_DIR}", flush=True)
    print(f"[BOOT] Database path: {DB_FILE} (exists: {DB_FILE.exists()})", flush=True)
    print(f"[BOOT] Session path: {SESSION_FILE} (exists: {SESSION_FILE.exists()})", flush=True)
    print(f"[BOOT] Screenshot dir: {SCREENSHOT_DIR} (exists: {SCREENSHOT_DIR.exists()})", flush=True)
    print(f"[BOOT] Promo link: {promo_link} | Batch: {batch_size} | Demo: {demo_mode}", flush=True)

    if not DB_FILE.exists():
        print(f"[!] FATAL: Database not found at {DB_FILE}. Aborting.", flush=True)
        return
    if not SESSION_FILE.exists():
        print(f"[!] FATAL: Session file not found at {SESSION_FILE}. Run --login first.", flush=True)
        return

    db = sqlite3.connect(str(DB_FILE))
    cursor = db.cursor()

    # ─── Database Pulse ───
    cursor.execute("SELECT COUNT(*) FROM targets")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT status, COUNT(*) FROM targets GROUP BY status")
    breakdown = cursor.fetchall()
    print(f"[BOOT] Database loaded. Total targets: {total}", flush=True)
    for status, count in breakdown:
        print(f"  [{status}]: {count}", flush=True)

    cursor.execute("SELECT COUNT(*) FROM targets WHERE status = 'pending'")
    pending_count = cursor.fetchone()[0]

    if pending_count == 0 and not demo_mode:
        print("[!] CRITICAL: Database is empty. Scrape targets before starting strike.", flush=True)
        print("[*] Tip: Use --demo to test with a hardcoded user ID.", flush=True)
        db.close()
        return

    cycle = 0
    proxy_fail_count = 0

    while True:
        print(f"\n=== [ OMNI-VIPER CYCLE {cycle + 1} INITIALIZED ] ===", flush=True)

        # Clear any stale signal on fresh cycle start
        if proxy_fail_count == 0:
            BOT_SIGNAL_FILE.unlink(missing_ok=True)

        # ─── Proxy Health Check ───
        proxy_url = CONFIG["PROXY"]
        try:
            proxy_host = proxy_url.split("@")[-1] if "@" in proxy_url else proxy_url.replace("http://", "")
            print(f"[DEBUG] Testing proxy: {proxy_host}...", flush=True)
            test_resp = requests.get(
                "https://httpbin.org/ip",
                proxies={"http": proxy_url, "https": proxy_url},
                timeout=15,
            )
            if test_resp.status_code == 407:
                proxy_fail_count += 1
                print(f"[ERROR] Proxy returned 407 Proxy Authentication Required. (fail {proxy_fail_count}/3)", flush=True)
                print("[ERROR] Check proxy credentials or whitelist this server's IP.", flush=True)
                if proxy_fail_count >= 3:
                    BOT_SIGNAL_FILE.write_text("STRIKE_PAUSED:proxy_auth_407")
                    print("[SIGNAL] STRIKE_PAUSED — 3 consecutive proxy auth failures. Halting strikes.", flush=True)
                await asyncio.sleep(60)
                cycle += 1
                continue
            elif test_resp.status_code >= 400:
                proxy_fail_count += 1
                print(f"[ERROR] Proxy returned HTTP {test_resp.status_code}. (fail {proxy_fail_count}/3)", flush=True)
                if proxy_fail_count >= 3:
                    BOT_SIGNAL_FILE.write_text(f"STRIKE_PAUSED:proxy_http_{test_resp.status_code}")
                    print("[SIGNAL] STRIKE_PAUSED — 3 consecutive proxy failures. Halting strikes.", flush=True)
                await asyncio.sleep(60)
                cycle += 1
                continue
            else:
                print(f"[DEBUG] Proxy alive. External IP: {test_resp.json().get('origin', 'unknown')}. Status: {test_resp.status_code}", flush=True)
                proxy_fail_count = 0  # Reset on success
                BOT_SIGNAL_FILE.unlink(missing_ok=True)
        except requests.exceptions.ProxyError as proxy_err:
            proxy_fail_count += 1
            err_str = str(proxy_err)
            if "407" in err_str:
                print(f"[ERROR] Proxy Authentication Required (407). (fail {proxy_fail_count}/3)", flush=True)
                print("[ERROR] Check proxy credentials or whitelist this server's IP.", flush=True)
            else:
                print(f"[ERROR] Proxy connection failed: {proxy_err} (fail {proxy_fail_count}/3)", flush=True)
            if proxy_fail_count >= 3:
                BOT_SIGNAL_FILE.write_text("STRIKE_PAUSED:proxy_connection_failed")
                print("[SIGNAL] STRIKE_PAUSED — 3 consecutive proxy failures. Halting strikes.", flush=True)
            await asyncio.sleep(60)
            cycle += 1
            continue
        except Exception as proxy_err:
            proxy_fail_count += 1
            print(f"[ERROR] Proxy connection failed: {proxy_err} (fail {proxy_fail_count}/3)", flush=True)
            if proxy_fail_count >= 3:
                BOT_SIGNAL_FILE.write_text("STRIKE_PAUSED:proxy_connection_failed")
                print("[SIGNAL] STRIKE_PAUSED — 3 consecutive proxy failures. Halting strikes.", flush=True)
            await asyncio.sleep(60)
            cycle += 1
            continue

        page = None  # Track for timeout screenshot
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True, proxy={"server": CONFIG["PROXY"]})
                context = await browser.new_context(
                    storage_state=str(SESSION_FILE),
                    viewport=STEALTH_VIEWPORT,
                    user_agent=STEALTH_UA,
                )
                page = await context.new_page()
                await stealth_async(page)
                print(f"[*] Browser launched. Viewport: {STEALTH_VIEWPORT['width']}x{STEALTH_VIEWPORT['height']}. Session loaded.", flush=True)

                # ─── Console Log Listener (catch Discord-side errors) ───
                page.on("console", lambda msg: print(f"[CONSOLE] [{msg.type}] {msg.text}", flush=True) if msg.type in ("error", "warning") else None)

                # Wait for Discord to fully load before any action
                print("[*] Navigating to Discord DMs (60s timeout)...", flush=True)
                response = await page.goto("https://discord.com/channels/@me", wait_until="networkidle", timeout=60000)

                # ─── Network Monitoring: log the HTTP status ───
                if response:
                    status = response.status
                    status_text = response.status_text
                    print(f"[DEBUG] Discord Load Status: {status} {status_text}", flush=True)
                    if status >= 400:
                        print(f"[ERROR] Discord returned HTTP {status}. Possible block or auth failure.", flush=True)
                        await page.screenshot(path=str(CYCLE_TIMEOUT_PATH), type="jpeg", quality=70)
                        print(f"[DEBUG] Error screenshot saved to {CYCLE_TIMEOUT_PATH}", flush=True)
                        await browser.close()
                        await asyncio.sleep(60)
                        cycle += 1
                        continue
                else:
                    print("[WARN] No response object from page.goto — possible redirect or abort.", flush=True)

                await asyncio.sleep(random.uniform(3, 5))
                await _capture_feed(page)

                # Debug screenshot — verify what the headless screen looks like
                await page.screenshot(path=str(DEBUG_SCREENSHOT_PATH), type="jpeg", quality=70)
                print("[*] Discord loaded. Debug render saved.", flush=True)

                # ─── Demo Mode: Single test message then exit ───
                if demo_mode:
                    print(f"\n--- [ DEMO MODE ] Sending test message to ID {DEMO_TEST_ID} ---", flush=True)
                    try:
                        await asyncio.sleep(3)
                        await _capture_feed(page)
                        print("[DEMO] Navigated to DMs. Attempting search...", flush=True)
                        await page.keyboard.press("Control+k")
                        await asyncio.sleep(2)
                        search_input = await page.wait_for_selector('[placeholder="Where would you like to go?"]', timeout=10000)
                        await search_input.type("@b1lin", delay=random.randint(110, 230))
                        await asyncio.sleep(5)
                        await page.keyboard.press("Enter")
                        await asyncio.sleep(8)
                        await _capture_feed(page)
                        await page.click('div[role="textbox"]')
                        await page.keyboard.type("Demo test from Sovereign bot.", delay=random.randint(80, 160))
                        await page.keyboard.press("Enter")
                        print("[DEMO] Test message sent!", flush=True)
                        await asyncio.sleep(3)
                        await _capture_feed(page)
                    except Exception as e:
                        print(f"[DEMO] Failed: {e}", flush=True)
                        await _capture_feed(page)
                    await browser.close()
                    db.close()
                    print("[DEMO] Demo complete. Exiting.", flush=True)
                    return

                # ─── Normal Operation ───
                predator = PredatorEngine(page, db)

                # 1. Check for replies (The Hammer)
                await predator.hammer_check()
                await _capture_feed(page)

                # 2. Strike new targets (The Hook)
                await predator.hook_strike(batch_size=batch_size)
                await _capture_feed(page)

                # 3. Rest
                nap = random.randint(300, 600)
                print(f"\n[*] Cycle complete. Resting browser for {round(nap/60, 1)}m...", flush=True)
                await browser.close()
                await asyncio.sleep(nap)

        except PlaywrightTimeout as te:
            print(f"[!] CYCLE TIMEOUT: {te}", flush=True)
            if page:
                try:
                    await page.screenshot(path=str(CYCLE_TIMEOUT_PATH), type="jpeg", quality=70)
                    print(f"[DEBUG] Timeout screenshot saved to {CYCLE_TIMEOUT_PATH}", flush=True)
                except Exception:
                    print("[DEBUG] Could not capture timeout screenshot (page may be dead).", flush=True)
            await asyncio.sleep(30)

        except Exception as e:
            print(f"[!] Cycle error: {e}", flush=True)
            if page:
                try:
                    await page.screenshot(path=str(CYCLE_TIMEOUT_PATH), type="jpeg", quality=70)
                    print(f"[DEBUG] Error screenshot saved to {CYCLE_TIMEOUT_PATH}", flush=True)
                except Exception:
                    pass
            await asyncio.sleep(30)

        cycle += 1
        if cycle % 10 == 0:
            print("[***] Extended Cool-down (15m) to avoid detection...", flush=True)
            await asyncio.sleep(900)

if __name__ == "__main__":
    if "--login" in sys.argv:
        asyncio.run(login_mode())
    elif "--manual" in sys.argv:
        asyncio.run(manual_login_mode())
    else:
        asyncio.run(main())  # handles --demo flag internally