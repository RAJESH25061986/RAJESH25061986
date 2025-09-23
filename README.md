# Nifty Supertrend & RSI Trading Bot

This project is an automated trading bot that implements a trend-following strategy on the Nifty index futures. It uses the Angel One API to fetch market data and execute trades.

## Strategy
The bot uses the following strategy on a 5-minute timeframe:
- **Buy Signal:**
  1. The candle is Green.
  2. The Supertrend indicator (10, 2) is Green (buy signal).
  3. The RSI indicator (14) is above 50.
- **Sell Signal:**
  1. The candle is Red.
  2. The Supertrend indicator (10, 2) is Red (sell signal).
  3. The RSI indicator (14) is below 50.
- **Trade Management:**
  - **Stop-Loss:** The low (for buy) or high (for sell) of the candle immediately preceding the signal candle.
  - **Target:** A 1:2 Risk-to-Reward ratio.
  - The bot automatically monitors the live price and exits the trade if the stop-loss or target is hit.

---

## Project Structure
- `main.py`: The main entry point to run the bot.
- `angel_one_client.py`: A client library to handle all interactions with the Angel One API.
- `strategy.py`: The core module containing the trading logic.
- `app_config.py`: **(IMPORTANT)** Your configuration file for API keys and settings.
- `requirements.txt`: A list of the required Python libraries.
- `README.md`: This setup guide.

---

## How to Set Up and Run

### Step 1: Create the Configuration File

This is the most important step. Create a file named `app_config.py` in the same directory as the other files. Copy the entire code block below and paste it into your `app_config.py` file.

```python
# Angel One API Credentials
API_KEY = "YOUR_API_KEY"
SECRET_KEY = "YOUR_SECRET_KEY"
CLIENT_ID = "YOUR_CLIENT_ID"
PASSWORD = "YOUR_LOGIN_PASSWORD"
TOTP_SECRET = "YOUR_TOTP_SECRET" # Your Time-based OTP secret key

# Trading Settings
TRADING_SYMBOL = "NIFTY"
TIMEFRAME = "5MINUTE"

# Strategy Parameters
SUPERTREND_PERIOD = 10
SUPERTREND_MULTIPLIER = 2
RSI_PERIOD = 14
RSI_MIDLINE = 50

# Risk Management
RISK_REWARD_RATIO = 2.0
LOT_SIZE = 50

# Bot Settings
# Set to True to log trades without executing them.
# Set to False to execute real trades.
PAPER_TRADING = True
```

**IMPORTANT:** You must replace the placeholder values (`"YOUR_API_KEY"`, etc.) with your actual Angel One API credentials.

### Step 2: Install Dependencies

Open your terminal or command prompt in the project directory and run the following command to install the necessary Python libraries:
```bash
pip install -r requirements.txt
```

### Step 3: Run the Bot

Once your configuration is set up and the dependencies are installed, you can run the bot with the following command:
```bash
python main.py
```

The bot will start, log in, and begin looking for trading opportunities. It is highly recommended to run it in `PAPER_TRADING = True` mode first to ensure everything is working as expected.
