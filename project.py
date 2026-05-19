"""
FIRE Engine
Implement an age-based glide path for portfolio rebalancing using SQLite
"""

import math
import sqlite3
import sys
from datetime import datetime
import yfinance as yf

"""User Configuration"""
BIRTH_YEAR = 1992
BASE_CURRENCY = "HKD"
DB_NAME = "portfolio.db"


def get_db_connection():
    """Establish connection to SQLite database"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def age_tier(age):
    """Determine the relevant age bracket for the glide path"""
    if age < 0:
        raise ValueError
    if 0 <= age < 40:
        return 30
    elif 40 <= age < 50:
        return 40
    elif 50 <= age < 65:
        return age
    elif 65 <= age <= 120:
        return 65
    else:
        raise ValueError


def read_glide_path(age):
    """Fetch target asset allocation from database for a specific age"""
    conn = get_db_connection()
    query = """
        SELECT ticker, target_percent
        FROM glide_path
        JOIN assets ON assets.id = glide_path.asset_id
        WHERE age = ? AND target_percent > 0
    """
    rows = conn.execute(query, (age,)).fetchall()
    conn.close()

    if not rows:
        sys.exit(f"Error: No glide path found for age {age}")

    targets = []
    for row in rows:
        targets.append({"ticker": row["ticker"], "percent": row["target_percent"]})
    return targets


def read_portfolio():
    """Calculate current holdings by summing all transactions"""
    conn = get_db_connection()
    query = """
        SELECT ticker, SUM(shares) as total_shares, currency
        FROM transactions
        JOIN assets ON assets.id = transactions.asset_id
        GROUP BY ticker
        HAVING total_shares > 0
    """
    rows = conn.execute(query).fetchall()
    conn.close()

    assets = []
    for row in rows:
        assets.append({
            "ticker": row["ticker"],
            "shares": float(row["total_shares"]),
            "currency": row["currency"]
        })
    return assets


def write_initial_portfolio(targets):
    """Setup wizard for first-time users to input holdings"""
    conn = get_db_connection()
    print("\n--- Initial Portfolio Setup ---")

    for t in targets:
        print(f"Verifying {t['ticker']}...")
        try:
            ticker_obj = yf.Ticker(t['ticker'])
            ticker_info = ticker_obj.info
            currency = ticker_info.get("currency")
            price = ticker_obj.history(period="1d")["Close"].iloc[-1]
        except Exception:
            currency = None

        if not currency:
            print(f"{t['ticker']} rejected: Could not verify data")
            continue

        print(f"{t['ticker']} verified, asset currency: {currency}")

        while True:
            try:
                shares = float(input(f"Input number of shares for {t['ticker']}: "))
                if shares < 0:
                    print("Please enter a positive amount")
                    continue
                break
            except ValueError:
                print("Invalid input")

        asset = conn.execute("SELECT id FROM assets WHERE ticker = ?", (t['ticker'],)).fetchone()
        if asset:
            # Record the transaction
            conn.execute("""
                INSERT INTO transactions (asset_id, type, shares, price_per_share)
                VALUES (?, 'BUY', ?, ?)
            """, (asset["id"], shares, price))

            # Seed the market_prices table
            conn.execute("""
                INSERT OR REPLACE INTO market_prices (asset_id, current_price, last_updated)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (asset["id"], price))

    conn.commit()
    conn.close()
    print("\nSetup complete, redirecting to main menu...")


def get_prices(assets, BASE_CURRENCY):
    """Fetch live market prices and update the database"""
    print(f"Updating prices to {BASE_CURRENCY}...")
    conn = get_db_connection()

    try:
        for asset in assets:
            ticker = yf.Ticker(asset["ticker"])
            stock_data = ticker.history(period="1d")

            if stock_data.empty:
                continue

            local_price = stock_data["Close"].iloc[-1]

            # Handle FX conversion if asset is not in base currency
            if asset["currency"] == BASE_CURRENCY:
                rate = 1.0
            else:
                fx = yf.Ticker(f"{asset['currency']}{BASE_CURRENCY}=X")
                fx_data = fx.history(period="1d")
                rate = fx_data["Close"].iloc[-1] if not fx_data.empty else 1.0

            asset["price"] = local_price * rate

            # Sync live price back to SQLite
            conn.execute("""
                UPDATE market_prices
                SET current_price = ?, last_updated = CURRENT_TIMESTAMP
                WHERE asset_id = (SELECT id FROM assets WHERE ticker = ?)
            """, (asset["price"], asset["ticker"]))

        conn.commit()
    finally:
        # Ensure connection is closed to prevent database locking
        conn.close()

    return assets


def cal_asset(assets, targets):
    """Calculate subtotal, current percentage, and drift from target"""
    for asset in assets:
        asset["subtotal"] = asset["shares"] * asset["price"]

    total = sum(asset["subtotal"] for asset in assets)
    if total == 0:
        sys.exit("\nPortfolio value is zero")

    for asset in assets:
        asset["percent"] = asset["subtotal"] / total
        target = 0
        for t in targets:
            if t["ticker"] == asset["ticker"]:
                target = t["percent"]
                break
        asset["target"] = target
        asset["diff"] = target - asset["percent"]

    return total, assets


def is_drift(diff, target):
    """Check if asset has drifted beyond the 5/25 rebalancing rule"""
    if target == 0:
        return True
    return abs(diff) > 0.05 or abs(diff) / target > 0.25


def cal_action(asset, total):
    """Calculate the number of shares needed to buy/sell to reach target"""
    trade_amount = total * asset["diff"]
    shares = math.floor(abs(trade_amount) / asset["price"])
    if shares == 0:
        return "HOLD"
    if trade_amount > 0:
        return f"BUY {shares} shares"
    else:
        return f"SELL {shares} shares"


def most_underweight(assets):
    """Find the asset furthest below its target allocation"""
    if not assets:
        return None
    top_asset = assets[0]
    for asset in assets:
        if asset["diff"] > top_asset["diff"]:
            top_asset = asset
    return top_asset


def cal_shares(contribution, asset):
    """Calculate how many shares can be bought with a specific cash amount"""
    shares = math.floor(contribution / asset["price"])
    if shares > 0:
        return f"You can buy {shares} shares of {asset['ticker']}"
    else:
        return f"{asset['ticker']} is the most underweight, but not enough cash to buy 1 share"


def show_target(targets):
    """Display suggested allocation for new users"""
    print(f"Suggested asset allocation at your age:\n")
    for t in targets:
        print(f"{t['ticker']}: {t['percent']:.0%}")
    while True:
        response = input("\nDo you want to input your current holding? (y/n) ")
        if response == "y":
            return True
        elif response == "n":
            return False
        else:
            print("Invalid Response")


def view_compo(assets, total):
    """Print current portfolio status and identify drift"""
    print(f"Current Portfolio Composition:\n")
    for asset in assets:
        if asset["target"] == 0:
            print(f"{asset['ticker']}: {asset['percent']:.2%} (target: 0%) SELL ALL")
        elif is_drift(asset["diff"], asset["target"]):
            suggestion = cal_action(asset, total)
            print(f"{asset['ticker']}: {asset['percent']:.2%} (target: {asset['target']:.0%}) {suggestion}")
        else:
            print(f"{asset['ticker']}: {asset['percent']:.2%} (target: {asset['target']:.0%}) ✅")
    input("\nPress Enter to return to menu")


def rebalance(assets, total):
    """Provide a summary of all trades needed to rebalance portfolio"""
    print(f"Rebalance Suggestion:\n")
    for asset in assets:
        suggestion = cal_action(asset, total)
        print(f"{asset['ticker']}: {suggestion}")
    input("\nPress Enter to return to menu")


def suggest(assets, BASE_CURRENCY):
    """Recommend which asset to buy based on a new cash injection"""
    print(f"Investment Suggestion:\n")
    while True:
        try:
            contribution = float(input(f"How much do you plan to invest in {BASE_CURRENCY}? $"))
            if contribution < 0:
                print("Please enter a positive amount")
                continue
            break
        except ValueError:
            print("Invalid input")

    best_buy = most_underweight(assets)
    if best_buy:
        suggestion = cal_shares(contribution, best_buy)
        print(suggestion)
    else:
        print(f"No underweight asset")
    input("\nPress Enter to return to menu")


def main_menu(targets, holdings, BASE_CURRENCY):
    """Main program loop and navigation"""
    data = get_prices(holdings, BASE_CURRENCY)
    total, assets = cal_asset(data, targets)

    while True:
        print(f"\nPortfolio total value: {BASE_CURRENCY} ${total:,.2f}")
        print("1. View Current Composition")
        print("2. Rebalance")
        print("3. Suggest Asset to Buy")
        print("4. Exit")
        choice = input("Choice: ")

        match choice:
            case "1":
                view_compo(assets, total)
            case "2":
                rebalance(assets, total)
            case "3":
                suggest(assets, BASE_CURRENCY)
            case "4":
                sys.exit("\nGoodbye!")
            case _:
                input("Invalid input, please choose 1/2/3/4 (Press Enter for re-input)")


def main():
    """Initialize application logic"""
    try:
        target_age = age_tier(datetime.now().year - BIRTH_YEAR)
    except ValueError:
        sys.exit("Not a valid birth year in configuration")

    targets = read_glide_path(target_age)
    holdings = read_portfolio()

    # If database is empty, start initial setup wizard
    if not holdings:
        if show_target(targets):
            write_initial_portfolio(targets)
            holdings = read_portfolio()
            main_menu(targets, holdings, BASE_CURRENCY)
        else:
            sys.exit("\nGoodbye!")
    else:
        main_menu(targets, holdings, BASE_CURRENCY)


if __name__ == "__main__":
    main()
