import logging
from SmartApi import SmartConnect
import pandas as pd
import app_config as config
import requests
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

class AngelOneClient:
    def __init__(self):
        """
        Initializes the Angel One client with credentials from the config file.
        """
        try:
            self.api_key = config.API_KEY
            self.secret_key = config.SECRET_KEY
            self.client_id = config.CLIENT_ID
            self.password = config.PASSWORD
            self.totp_secret = config.TOTP_SECRET

            self.smart_api = SmartConnect(self.api_key)
            log.info("SmartConnect object initialized successfully.")

            self.session_data = None
            self.feed_token = None
            self.jwt_token = None

        except Exception as e:
            log.error(f"Error during client initialization: {e}")
            raise

    def login(self):
        """
        Logs into the Angel One API and generates a session.
        Stores the session data, feed token, and JWT token.
        """
        log.info("Attempting to log in...")
        try:
            # Generate a session using the credentials
            data = self.smart_api.generateSession(
                self.client_id,
                self.password,
                self.smart_api.get_totp(self.totp_secret)
            )

            if data['status'] and data['data'] is not None:
                self.session_data = data['data']
                self.jwt_token = self.session_data['jwtToken']
                self.feed_token = self.smart_api.getfeedToken()

                log.info("Login successful!")
                log.info(f"Welcome, {self.session_data.get('clientName', 'user')}")
                return True
            else:
                log.error(f"Login failed. Reason: {data.get('message', 'Unknown error')}")
                return False

        except Exception as e:
            log.error(f"An exception occurred during login: {e}")
            return False

    def get_instrument_details(self, name='NIFTY'):
        """
        Fetches the instrument list and finds the futures contract with the nearest expiry.

        :param name: The name of the instrument (e.g., 'NIFTY').
        :return: A dictionary with 'symbol', 'token', and 'expiry' if found, else None.
        """
        log.info(f"Fetching instrument list to find nearest expiry for {name} futures...")

        instrument_url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
        try:
            response = requests.get(instrument_url, timeout=10)
            response.raise_for_status()
            instrument_list = response.json()
            log.info(f"Successfully fetched {len(instrument_list)} instruments.")
        except requests.exceptions.RequestException as e:
            log.error(f"Failed to download instrument list: {e}")
            return None

        futures_contracts = []
        today = datetime.now()

        for instrument in instrument_list:
            if instrument.get('name') == name and instrument.get('instrumenttype') == 'FUTIDX':
                try:
                    # Parse the expiry date, format is DDMMMYYYY (e.g., 26SEP2024)
                    expiry_date = datetime.strptime(instrument['expiry'], '%d%b%Y')
                    if expiry_date > today:
                        futures_contracts.append({
                            'symbol': instrument['symbol'],
                            'token': instrument['token'],
                            'expiry': expiry_date
                        })
                except (ValueError, KeyError) as e:
                    log.debug(f"Could not parse instrument, skipping. Reason: {e}")
                    continue

        if not futures_contracts:
            log.error(f"No active futures contracts found for {name}.")
            return None

        # Find the contract with the nearest expiry date
        nearest_contract = min(futures_contracts, key=lambda x: x['expiry'])
        log.info(f"Found nearest expiry instrument: {nearest_contract}")

        return nearest_contract

    def get_ltp(self, symbol, token, exchange="NFO"):
        """
        Fetches the Last Traded Price (LTP) for a given instrument.

        :param symbol: The trading symbol of the instrument.
        :param token: The token of the instrument.
        :param exchange: The exchange of the instrument (e.g., 'NFO', 'NSE').
        :return: The LTP as a float, or None if an error occurs.
        """
        log.debug(f"Fetching LTP for {symbol} ({token})")
        try:
            # The ltpData function seems to work best with these params
            response = self.smart_api.ltpData(exchange, symbol, token)

            if response.get('status') and response.get('data', {}).get('ltp'):
                ltp = response['data']['ltp']
                log.debug(f"LTP for {symbol}: {ltp}")
                return float(ltp)
            else:
                log.error(f"Could not fetch LTP for {symbol}: {response.get('message', 'No data')}")
                return None
        except Exception as e:
            log.error(f"An exception occurred while fetching LTP for {symbol}: {e}")
            return None

    def get_historical_data(self, symbol_token, from_date, to_date, interval='FIVE_MINUTE'):
        """
        Fetches historical candle data for a given symbol token.

        :param symbol_token: The token of the symbol (e.g., "26000" for NIFTY).
        :param from_date: The start date in 'YYYY-MM-DD HH:MM' format.
        :param to_date: The end date in 'YYYY-MM-DD HH:MM' format.
        :param interval: The candle interval (e.g., 'FIVE_MINUTE').
        :return: A pandas DataFrame with historical data, or None if an error occurs.
        """
        log.info(f"Fetching historical data for token {symbol_token} from {from_date} to {to_date}")
        try:
            params = {
                "exchange": "NFO", # Futures data is on the NFO exchange
                "symboltoken": symbol_token,
                "interval": interval,
                "fromdate": from_date,
                "todate": to_date
            }
            raw_data = self.smart_api.getCandleData(params)

            if raw_data['status'] and raw_data['data'] is not None:
                df = pd.DataFrame(raw_data['data'], columns=['datetime', 'open', 'high', 'low', 'close', 'volume'])
                df['datetime'] = pd.to_datetime(df['datetime'])
                log.info(f"Successfully fetched {len(df)} candles.")
                return df
            else:
                log.error(f"Failed to fetch historical data: {raw_data.get('message', 'No data')}")
                return None
        except Exception as e:
            log.error(f"An exception occurred while fetching historical data: {e}")
            return None

    def place_order(self, symbol, token, quantity, transaction_type, order_type='MARKET', product_type='INTRADAY'):
        """
        Places an order.

        :param symbol: The trading symbol (e.g., 'NIFTY').
        :param token: The symbol token.
        :param quantity: The number of shares/lots.
        :param transaction_type: 'BUY' or 'SELL'.
        :param order_type: 'MARKET' or 'LIMIT'.
        :param product_type: 'INTRADAY', 'DELIVERY', etc.
        :return: The order ID if successful, else None.
        """
        log.info(f"Placing {transaction_type} order for {quantity} of {symbol}...")
        try:
            params = {
                "variety": "NORMAL",
                "tradingsymbol": symbol, # Use the dynamically fetched symbol directly
                "symboltoken": token,
                "transactiontype": transaction_type,
                "exchange": "NFO", # Futures are also in the NFO segment
                "ordertype": order_type,
                "producttype": product_type,
                "duration": "DAY",
                "quantity": quantity
            }
            response = self.smart_api.placeOrder(params)
            if response and response.get('status'):
                order_id = response.get('data', {}).get('orderid')
                log.info(f"Successfully placed order. Order ID: {order_id}")
                return order_id
            else:
                log.error(f"Failed to place order: {response.get('message', 'Unknown error')}")
                return None
        except Exception as e:
            log.error(f"An exception occurred while placing order: {e}")
            return None

    def logout(self):
        """
        Logs out from the Angel One session.
        """
        log.info("Attempting to log out...")
        try:
            if self.session_data:
                self.smart_api.terminateSession(self.client_id)
                log.info("Logout successful.")
            else:
                log.warning("No active session to log out from.")
        except Exception as e:
            log.error(f"An exception occurred during logout: {e}")

# Example usage (for testing purposes)
if __name__ == '__main__':
    # This block will only run when the script is executed directly
    # It allows for testing the client's login functionality

    # IMPORTANT: Fill in your credentials in app_config.py before running this
    if config.API_KEY == "YOUR_API_KEY":
        log.error("Please fill in your API credentials in the 'app_config.py' file.")
    else:
        client = AngelOneClient()
        if client.login():
            # You can add more test calls here in the future
            client.logout()
