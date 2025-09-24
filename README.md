# Intelligent Iron Condor Trading Bot

This project is an automated trading bot that implements a sophisticated Iron Condor options strategy on Nifty. It uses the Angel One API to fetch market data and execute trades.

## Strategy Overview
The bot is designed to trade a daily Iron Condor with the following logic:

1.  **Strike Selection:**
    *   At the start of each day, the bot calculates the **Daily Pivot Points** (R1, S1) based on the previous day's data.
    *   It selects a Put option to **SELL** near Support 1 (S1) and a Call option to **SELL** near Resistance 1 (R1).

2.  **Hedge Selection:**
    *   For each sold option, the bot finds a hedging option to **BUY**.
    *   The hedge is selected by finding an option whose premium is approximately **50% of the sold option's premium**, within a 2% strike price distance.

3.  **Entry Trigger:**
    *   The bot continuously monitors the two options selected for selling.
    *   It enters the entire 4-legged Iron Condor trade only when the premium of **BOTH** the sold Put AND the sold Call are **below their respective 15-minute VWAP**.

4.  **Risk Management & Exits:**
    *   The bot calculates Profit & Loss based on the estimated **total margin blocked** for the trade.
    *   **Take Profit:** The entire 4-leg position is closed if it hits a **1.5% profit** on the margin.
    *   **Stop-Loss:** The entire position is closed if it hits a **2.5% loss** on the margin.

---

## Project Structure
- `main.py`: The main entry point to run the bot.
- `angel_one_client.py`: A client library for all Angel One API interactions.
- `strategy.py`: The core module for pivot calculations, option selection, and VWAP checks.
- `app_config.py`: **(IMPORTANT)** Your configuration file for API keys and all strategy parameters.
- `requirements.txt`: A list of the required Python libraries.

---

## How to Set Up and Run

### Step 1: Create the Configuration File
Create a file named `app_config.py` in the same directory. Copy the entire code block below and paste it into your `app_config.py` file.

```python
# --- Angel One API Credentials ---
API_KEY = "YOUR_API_KEY"
SECRET_KEY = "YOUR_SECRET_KEY"
CLIENT_ID = "YOUR_CLIENT_ID"
PASSWORD = "YOUR_LOGIN_PASSWORD"
TOTP_SECRET = "YOUR_TOTP_SECRET"

# --- General Trading Settings ---
TRADING_INSTRUMENT = "NIFTY"
# IMPORTANT: Set this to the correct weekly expiry date you want to trade
# Format: DDMMMYYYY, e.g., "26SEP2025"
OPTION_EXPIRY = "26SEP2025"

# --- Iron Condor Strategy Parameters ---
# Timeframe for calculating VWAP
VWAP_TIMEFRAME = "FIFTEEN_MINUTE"

# Rules for selecting the hedge leg
HEDGE_PREMIUM_RATIO = 0.5 # Buy hedge with premium at 50% of sold premium
HEDGE_STRIKE_DISTANCE_PERCENT = 2.0 # Max 2% strike distance for the hedge

# --- Risk Management and Exit Rules ---
# Profit and Loss percentages are based on the margin blocked for the trade
PROFIT_PERCENT_MARGIN = 1.5
SL_PERCENT_MARGIN = 2.5
# Estimated margin blocked per lot for a Nifty Iron Condor.
# This should be a conservative estimate.
ESTIMATED_MARGIN_PER_LOT = 45000
LOT_SIZE = 50

# --- Bot Settings ---
PAPER_TRADING = True
```

**IMPORTANT:** You must replace the placeholder values for your API credentials and set the `OPTION_EXPIRY` to a valid date.

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Run the Bot
```bash
python main.py
```
The bot will start, log in, and begin its daily setup and monitoring routine. It is highly recommended to run it in `PAPER_TRADING = True` mode first.
