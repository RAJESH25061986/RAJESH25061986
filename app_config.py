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
OPTION_EXPIRY = "28OCT2025"

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
ESTIMATED_MARGIN_PER_LOT = 75000
LOT_SIZE = 75

# --- Bot Settings ---
PAPER_TRADING = True



