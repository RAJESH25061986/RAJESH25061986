import logging
from SmartApi import SmartConnect
import pandas as pd
import app_config as config
import requests
from datetime import datetime, timedelta

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
        """
        log.info("Attempting to log in...")
        try:
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
                return True
            else:
                log.error(f"Login failed. Reason: {data.get('message', 'Unknown error')}")
                return False

        except Exception as e:
            log.error(f"An exception occurred during login: {e}")
            return False

    def get_daily_ohlc(self, symbol_token="26000-NSE"): # Nifty Index token
        """
        Fetches the previous day's OHLC data for pivot calculation.
        Note: The token for Nifty index is different from futures/options.
        This may need to be looked up from the instrument list if it changes.
        """
        log.info(f"Fetching previous day OHLC for token {symbol_token}")
        try:
            # We need to find the actual token for the Nifty index from the instrument list
            # For simplicity, we assume a known token format here, but a robust implementation
            # would search the instrument list for the underlying index.
            # This is a simplification to avoid another full instrument list scan.

            # Find the last trading day, skipping weekends.
            today = datetime.now()
            # If today is Monday, the last trading day was Friday (3 days ago).
            # If Sunday, 2 days ago. Otherwise, 1 day ago.
            days_to_subtract = 1
            if today.weekday() == 0: # Monday
                days_to_subtract = 3
            elif today.weekday() == 6: # Sunday
                days_to_subtract = 2

            last_trading_day = today - timedelta(days=days_to_subtract)

            # Fetch data for a range to ensure we get the last candle.
            to_date = last_trading_day.strftime('%Y-%m-%d 23:59')
            from_date = (last_trading_day - timedelta(days=1)).strftime('%Y-%m-%d 00:00')

            params = {
                "exchange": "NSE",
                "symboltoken": "26000", # Nifty Index Token
                "interval": "ONE_DAY",
                "fromdate": from_date,
                "todate": to_date
            }
            raw_data = self.smart_api.getCandleData(params)

            if raw_data['status'] and raw_data['data']:
                # Return the last candle's data
                last_day = raw_data['data'][-1]
                return {'high': last_day[2], 'low': last_day[3], 'close': last_day[4]}
            else:
                log.error(f"Failed to fetch daily OHLC data: {raw_data.get('message', 'No data')}")
                return None
        except Exception as e:
            log.error(f"An exception occurred while fetching daily OHLC data: {e}")
            return None

    def get_option_chain(self, name, expiry_date):
        """
        Fetches the option chain for a given instrument and expiry date.
        It filters the master instrument list to find all relevant CE and PE options.
        """
        log.info(f"Fetching option chain for {name} with expiry {expiry_date}...")

        instrument_url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
        try:
            response = requests.get(instrument_url, timeout=10)
            response.raise_for_status()
            instrument_list = response.json()
        except requests.exceptions.RequestException as e:
            log.error(f"Failed to download instrument list: {e}")
            return None

        option_chain = {'calls': [], 'puts': []}
        for instrument in instrument_list:
            if instrument.get('name') == name and instrument.get('instrumenttype') == 'OPTIDX' and instrument.get('expiry') == expiry_date:
                try:
                    strike = float(instrument['strike']) / 100.0
                    option_type = instrument['opttype']

                    option_details = {
                        'symbol': instrument['symbol'],
                        'token': instrument['token'],
                        'strike': strike
                    }

                    if option_type == 'CE':
                        option_chain['calls'].append(option_details)
                    elif option_type == 'PE':
                        option_chain['puts'].append(option_details)
                except (ValueError, KeyError) as e:
                    log.debug(f"Could not parse option instrument, skipping. Reason: {e}")
                    continue

        log.info(f"Found {len(option_chain['calls'])} Calls and {len(option_chain['puts'])} Puts.")
        return option_chain

    def get_historical_data(self, symbol_token, interval, from_date, to_date):
        """
        Fetches historical candle data.
        """
        log.info(f"Fetching historical data for token {symbol_token}...")
        try:
            params = {
                "exchange": "NFO",
                "symboltoken": symbol_token,
                "interval": interval,
                "fromdate": from_date,
                "todate": to_date
            }
            raw_data = self.smart_api.getCandleData(params)

            if raw_data['status'] and raw_data['data']:
                df = pd.DataFrame(raw_data['data'], columns=['datetime', 'open', 'high', 'low', 'close', 'volume'])
                df['datetime'] = pd.to_datetime(df['datetime'])
                return df
            else:
                log.error(f"Failed to fetch historical data: {raw_data.get('message', 'No data')}")
                return None
        except Exception as e:
            log.error(f"An exception occurred while fetching historical data: {e}")
            return None

    def get_ltp(self, symbol, token, exchange="NFO"):
        """
        Fetches the Last Traded Price (LTP) for a given instrument.
        """
        log.debug(f"Fetching LTP for {symbol} ({token})")
        try:
            response = self.smart_api.ltpData(exchange, symbol, token)
            if response.get('status') and response.get('data', {}).get('ltp'):
                return float(response['data']['ltp'])
            else:
                log.error(f"Could not fetch LTP for {symbol}: {response.get('message', 'No data')}")
                return None
        except Exception as e:
            log.error(f"An exception occurred while fetching LTP for {symbol}: {e}")
            return None

    def place_order(self, symbol, token, quantity, transaction_type, order_type='MARKET', product_type='INTRADAY', exchange="NFO"):
        """
        Places a single order.
        """
        log.info(f"Placing {transaction_type} order for {quantity} of {symbol}...")
        try:
            params = {
                "variety": "NORMAL",
                "tradingsymbol": symbol,
                "symboltoken": token,
                "transactiontype": transaction_type,
                "exchange": exchange,
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
