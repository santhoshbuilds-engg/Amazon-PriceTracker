import argparse
import json
import logging
import os
import re
import sqlite3
import urllib.request
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

LOG = logging.getLogger("tracker")
TZ = ZoneInfo("Asia/Kolkata")

def parse_price(text):
    m = re.fullmatch(r"\s*₹\s*([0-9][0-9,]*(?:\.\d{1,2})?)\s*", text)
    if not m:
        return None
    value = Decimal(m.group(1).replace(",", ""))
    return int(value * 100) if value > 0 else None

def qualifies(price, target):
    return price is not None and price <= target * 100

def scrape(page, product):
    url = "https://www.amazon.in/dp/" + product["asin"]
    response = page.goto(url, wait_until="domcontentloaded", timeout=45000)
    if not response or response.status >= 400:
        raise RuntimeError("HTTP " + str(response.status if response else "unknown"))
    if page.locator("#captchacharacters, form[action*='validateCaptcha']").count():
        raise RuntimeError("CAPTCHA; stopping")
    if not re.search(r"/(?:dp|gp/product)/" + re.escape(product["asin"]) + r"(?:[/?]|$)", page.url):
        raise RuntimeError("Unexpected product URL")
    title = page.locator("#productTitle").first.inner_text(timeout=10000)
    if not all(word.casefold() in title.casefold() for word in product["title_contains"]):
        raise RuntimeError("Product title mismatch")
    if not page.locator("#add-to-cart-button, #buy-now-button").first.is_visible():
        raise RuntimeError("No visible purchase button")
    prices = page.locator("#corePrice_feature_div .a-price:not(.a-text-price) .a-offscreen, #corePriceDisplay_desktop_feature_div .a-price:not(.a-text-price) .a-offscreen").all_text_contents()
    values = {v for t in prices if (v := parse_price(t)) is not None}
    if len(values) != 1:
        raise RuntimeError("Missing or ambiguous price")
    offers = []
    for t in page.locator("#offers_feature_div, #instantBankDiscount_feature_div, #vpcButton").all_inner_texts():
        if "hdfc" in t.casefold():
            offers.append(t.strip()[:2000])
    return values.pop(), "\n".join(offers)

def notify(message):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat = os.environ["TELEGRAM_CHAT_ID"]
    data = json.dumps({"chat_id": chat, "text": message}).encode()
    req = urllib.request.Request("https://api.telegram.org/bot" + token + "/sendMessage",
                                 data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            if not json.load(response).get("ok"):
                raise RuntimeError("Telegram rejected message")
    except Exception:
        raise RuntimeError("Telegram delivery failed") from None

def run(dry_run=False):
    from playwright.sync_api import sync_playwright
    config = json.loads(Path(os.environ.get("CONFIG_PATH", "products.json")).read_text())
    path = Path(os.environ.get("DB_PATH", "data/history.sqlite"))
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db, sync_playwright() as pw:
        db.execute("CREATE TABLE IF NOT EXISTS checks (asin TEXT, checked_at TEXT, price INTEGER, offers TEXT, status TEXT)")
        db.execute("CREATE TABLE IF NOT EXISTS alerts (asin TEXT PRIMARY KEY, price INTEGER)")
        browser = pw.chromium.launch()
        try:
            for product in config:
                asin = product["asin"]
                if not re.fullmatch(r"[A-Z0-9]{10}", asin):
                    LOG.warning("Invalid ASIN; skipping")
                    continue
                now = datetime.now(TZ).isoformat()
                context = browser.new_context(locale="en-IN", timezone_id="Asia/Kolkata")
                try:
                    price, offers = scrape(context.new_page(), product)
                    db.execute("INSERT INTO checks VALUES (?,?,?,?,?)", (asin, now, price, offers, "ok"))
                    db.commit()
                    LOG.info("%s: INR %.2f; HDFC text present=%s", asin, price/100, bool(offers))
                    # A visible bank advertisement does not establish card eligibility.
                    # Do not infer a discounted checkout price from it.
                    if not qualifies(price, product["target_inr"]):
                        if not dry_run:
                            db.execute("DELETE FROM alerts WHERE asin=?", (asin,))
                            db.commit()
                        continue
                    previous = db.execute("SELECT price FROM alerts WHERE asin=?", (asin,)).fetchone()
                    if previous and previous[0] == price:
                        continue
                    message = f"{product['name']}\nListed price: INR {price/100:,.2f}\nTarget: INR {product['target_inr']}\nHDFC eligibility and checkout discounts not verified.\nhttps://www.amazon.in/dp/{asin}"
                    if dry_run:
                        LOG.info("Dry run: qualifying price; no notification")
                    else:
                        notify(message)
                        db.execute("INSERT OR REPLACE INTO alerts VALUES (?,?)", (asin, price))
                        db.commit()
                except Exception as exc:
                    LOG.warning("%s: check failed (%s)", asin, type(exc).__name__)
                    db.execute("INSERT INTO checks VALUES (?,?,?,?,?)", (asin, now, None, "", str(exc)[:200] if isinstance(exc, RuntimeError) else type(exc).__name__))
                    db.commit()
                finally:
                    context.close()
        finally:
            browser.close()

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.once or args.dry_run:
        run(args.dry_run)
    else:
        from apscheduler.schedulers.blocking import BlockingScheduler
        scheduler = BlockingScheduler(timezone=TZ)
        scheduler.add_job(run, "cron", hour=8, minute=0, max_instances=1, coalesce=True)
        LOG.info("Scheduled daily at 08:00 IST")
        scheduler.start()

if __name__ == "__main__":
    main()
