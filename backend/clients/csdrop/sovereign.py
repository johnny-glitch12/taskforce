import asyncio, random, sqlite3, json, os, time
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

# ==========================================
# I. CONFIGURATION (Keep your site/links here)
# ==========================================
CONFIG = {
    "PROXY": "http://spzi6md7ie:4u_eyh8sZM3KElhty2@gate.decodo.com:10010",
    "DB_PATH": "omni_viper_v8.db",
    "SESSION_FILE": "discord_session.json",
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
        print("    [*] Lurking (Session Warming)...")
        servers = await page.query_selector_all('div[role="treeitem"]')
        if servers:
            await random.choice(servers).click()
            await asyncio.sleep(random.randint(5, 10))
        await page.click('a[aria-label="Direct Messages"]', timeout=5000)
    except: pass

async def human_search_and_click(page, username):
    """Uses Ctrl+K and '@' prefix with jitter to bypass Captchas."""
    try:
        print(f"    [*] Triggering Stealth Search for @{username}...")
        await asyncio.sleep(random.uniform(1.5, 3.5))
        await page.keyboard.press("Control+k")
        await asyncio.sleep(random.uniform(1.5, 2.5))
        search_input = await page.wait_for_selector('[placeholder="Where would you like to go?"]', timeout=10000)
        await search_input.type("@", delay=random.randint(200, 450))
        await asyncio.sleep(random.uniform(0.8, 1.5))
        await search_input.type(username, delay=random.randint(110, 230))
        await asyncio.sleep(random.uniform(4, 6)) # Filter time
        await page.keyboard.press("Enter")
        await asyncio.sleep(random.randint(8, 12))
        return True
    except:
        await page.keyboard.press("Escape")
        return False

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
        if not targets: return

        print(f"\n--- [ PHASE 1: THE HAMMER ] (Checking {len(targets)} replies) ---")
        for u_id, u_name in targets:
            try:
                print(f"    [*] Scanning @{u_name}...")
                await self.page.goto("https://discord.com/channels/@me", wait_until="domcontentloaded")
                if not await human_search_and_click(self.page, u_name): continue

                await asyncio.sleep(random.randint(5, 8))
                msgs = await self.page.query_selector_all('li[class*="message_"]')
                content = await self.page.content()

                # Logic: If total messages > 1 and we haven't dropped our link yet
                if len(msgs) >= 2 and CONFIG["LINKS"]["SITE"] not in content:
                    print(f"    [!] REAL REPLY confirmed from @{u_name}!")
                    msg = random.choice(PROMO_TEMPLATES).format(site=CONFIG["LINKS"]["SITE"], link=CONFIG["LINKS"]["PROMO"])
                    await self.page.click('div[role="textbox"]')
                    await asyncio.sleep(random.uniform(4, 7)) 
                    await self.page.keyboard.type(msg, delay=random.randint(80, 160))
                    await self.page.keyboard.press("Enter")
                    self.cursor.execute("UPDATE targets SET status = 'completed' WHERE user_id = ?", (u_id,))
                    self.db.commit()
                    await asyncio.sleep(random.randint(15, 25))
            except: continue

    async def hook_strike(self, batch_size=10):
        """PHASE 2: Strikes exactly 10 new people as requested."""
        self.cursor.execute("SELECT user_id, username FROM targets WHERE status = 'pending' LIMIT ?", (batch_size,))
        pending = self.cursor.fetchall()
        if not pending: 
            print("[*] Queue Empty. Refuel needed via Dashboard.")
            return

        print(f"\n--- [ PHASE 2: THE HOOK ] (Striking batch of {len(pending)}) ---")
        for u_id, u_name in pending:
            try:
                print(f"[*] Striking: @{u_name}")
                await self.page.goto("https://discord.com/channels/@me", wait_until="domcontentloaded")
                if not await human_search_and_click(self.page, u_name): continue

                try:
                    wave_btn = await self.page.wait_for_selector('button:has-text("Wave")', timeout=8000)
                    await wave_btn.click()
                    print("    [+++] WAVE SENT")
                    self.cursor.execute("UPDATE targets SET status = 'hooked' WHERE user_id = ?", (u_id,))
                except:
                    # Text Fallback
                    msg = random.choice(HOOK_TEMPLATES).format(username=u_name)
                    await self.page.click('div[role="textbox"]')
                    await self.page.keyboard.type(msg, delay=random.randint(80, 160))
                    await self.page.keyboard.press("Enter")
                    print("    [+++] TEXT HOOK SENT")
                    self.cursor.execute("UPDATE targets SET status = 'hooked' WHERE user_id = ?", (u_id,))
                
                self.db.commit()
                await human_lurk(self.page)
                # Nap inside the batch
                await asyncio.sleep(random.randint(45, 90))
            except: continue

# ==========================================
# IV. THE INFINITE LOOP MAIN
# ==========================================
async def main():
    db = sqlite3.connect(CONFIG["DB_PATH"])
    cycle = 0

    while True: # THIS IS THE INFINITE LOOP
        print(f"\n=== [ OMNI-VIPER CYCLE {cycle + 1} INITIALIZED ] ===")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False, proxy={"server": CONFIG["PROXY"]})
            context = await browser.new_context(storage_state=CONFIG["SESSION_FILE"])
            page = await context.new_page()
            await Stealth().apply_stealth_async(page)
            
            predator = PredatorEngine(page, db)

            # 1. First, check for any and all replies (The Hammer)
            await predator.hammer_check()
            
            # 2. Then, strike 10 new targets (The Hook)
            await predator.hook_strike(batch_size=10)
            
            # 3. Rest the system
            nap = random.randint(300, 600)
            print(f"\n[*] Cycle complete. Resting browser for {round(nap/60, 1)}m...")
            await browser.close()
            await asyncio.sleep(nap)
            
        cycle += 1
        if cycle % 10 == 0:
            print("[***] Extended Cool-down (15m) to avoid detection...")
            await asyncio.sleep(900)

if __name__ == "__main__":
    asyncio.run(main())