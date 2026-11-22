# Amazon Price Tracker

Personal homelab MVP. Python, Playwright, Docker Compose, SQLite and Telegram. Checks configured Amazon India ASINs daily at 08:00 IST. Only sends alerts when an unambiguous, purchasable listing price is at or below the configured threshold. Repeated identical qualifying prices are suppressed until a verified above-target price occurs.

## Important limitations

Amazon may restrict automated access. Respect applicable terms and stop on CAPTCHA or HTTP errors; no bypass, rotating proxies or account login. The next scheduled check is the backoff. Visible HDFC offer text is recorded locally in SQLite, but eligibility, minimum spend, EMI and effective checkout price are not automatically verified. This MVP intentionally does NOT send HDFC-only alerts or infer discount amounts. Confirm card offers manually. Selectors may need maintenance. No live Amazon or Telegram integration test has been performed by the author. Use only where permitted.

## Setup on the Docker VM

Clone this repository into a project directory on your VM:

    git clone https://github.com/santhoshbuilds-engg/Amazon-PriceTracker.git
    cd Amazon-PriceTracker
    cp .env.example .env
    chmod 600 .env

Create a Telegram bot using @BotFather, open a chat with it and send /start. Obtain your chat ID using the Telegram Bot API getUpdates locally; keep the token private. Edit .env and populate both variables. Never commit .env.

Build the image (installs browser-compatible dependencies):

    docker compose build

Run a one-shot check without alerts:

    docker compose run --rm tracker python tracker.py --dry-run

Run one real check with alerts enabled (only if you want to test deal delivery):

    docker compose run --rm tracker python tracker.py --once

Start the daily scheduler:

    docker compose up -d
    docker compose logs -f tracker

The named volume persists SQLite price history and notification state across restarts. Run only one instance at a time. Stop with docker compose down (do not add -v unless you want to delete history).

## Configuration

Edit products.json to add additional ASINs, title checks and target prices in INR. Default is Bosch GSB 600 ASIN B0CHBV2RVJ at INR 4000. Restart the service after code changes; product config is reloaded on each check.

## Unit tests

From the repository root with Python 3.10+:

    python -m unittest discover -s tests

Tests cover price parsing and threshold decisions. Docker build and live checks are separate verification steps.

## Next milestone

Add conservative product-specific HDFC terms extraction and explicit eligibility rules, with saved page fixtures and tests, before enabling bank-only notifications. Do not store card numbers or account credentials.
