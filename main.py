import time
import logging
from datetime import datetime, timedelta
import app_config as config
from angel_one_client import AngelOneClient
from strategy import check_strategy_signal

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

def run_bot():
    """
    Main function to run the trading bot.
    """
    log.info("Starting the trading bot...")

    # Initialize the API client
    client = AngelOneClient()

    # --- Login ---
    # Check for placeholder credentials first
    if config.API_KEY == "YOUR_API_KEY":
        log.error("API credentials are not configured. Please fill them in 'app_config.py'.")
        return

    if not client.login():
        log.error("Login failed. Exiting bot.")
        return

    # --- Get Instrument Details ---
    log.info("Fetching Nifty futures instrument details...")
    nifty_instrument = client.get_instrument_details(name='NIFTY')
    if nifty_instrument is None:
        log.error("Could not find Nifty futures instrument details. Exiting bot.")
        return
    log.info(f"Successfully fetched instrument: {nifty_instrument}")

    log.info("Bot is running. Waiting for trading signals...")

    # --- Main Loop ---
    active_trade = None

    while True:
        try:
            now = datetime.now()
            # 1. Check if it's market hours
            if not (datetime.strptime("09:15", "%H:%M").time() < now.time() < datetime.strptime("15:30", "%H:%M").time()):
                log.info("Outside market hours. Sleeping until 9:15 AM.")
                time.sleep(60)
                continue

            # 2. Core Logic: Check for active trade or look for a new one
            if active_trade is None:
                # --- LOOK FOR A NEW TRADE ---
                log.info("Looking for a new trade signal...")

                # Fetch historical data every 5 minutes
                to_date = now.strftime('%Y-%m-%d %H:%M')
                from_date = (now - timedelta(days=5)).strftime('%Y-%m-%d %H:%M')

                historical_data = client.get_historical_data(
                    symbol_token=nifty_instrument['token'],
                    from_date=from_date,
                    to_date=to_date,
                    interval='FIVE_MINUTE'
                )

                if historical_data is None or historical_data.empty:
                    log.warning("Could not fetch historical data. Retrying in 1 minute.")
                    time.sleep(60)
                    continue

                signal, stop_loss = check_strategy_signal(historical_data)

                if signal in ['BUY', 'SELL']:
                    log.info(f"--- New Trade Signal: {signal} on last closed candle ---")

                    # Get live price for realistic entry
                    entry_price = client.get_ltp(symbol=nifty_instrument['symbol'], token=nifty_instrument['token'])
                    if entry_price is None:
                        log.error("Could not fetch LTP for entry. Skipping trade.")
                        time.sleep(20) # Wait before trying again
                        continue

                    risk = abs(entry_price - stop_loss)
                    target = entry_price + (risk * config.RISK_REWARD_RATIO) if signal == 'BUY' else entry_price - (risk * config.RISK_REWARD_RATIO)

                    log.info(f"Attempting Entry at LTP: {entry_price}, SL: {stop_loss}, Target: {target}")

                    if config.PAPER_TRADING:
                        log.info("PAPER TRADING: Mock trade opened.")
                        active_trade = {"signal": signal, "entry": entry_price, "sl": stop_loss, "target": target}
                    else:
                        log.info("REAL TRADING: Placing entry order...")
                        order_id = client.place_order(
                            symbol=nifty_instrument['symbol'], token=nifty_instrument['token'],
                            quantity=config.LOT_SIZE, transaction_type=signal.upper()
                        )
                        if order_id:
                            active_trade = {"signal": signal, "entry": entry_price, "sl": stop_loss, "target": target, "id": order_id}
                        else:
                            log.error("Failed to place entry order.")

                # Wait before checking for a new signal again
                time.sleep(60 * 5)

            else:
                # --- MANAGE THE ACTIVE TRADE ---
                log.info(f"Managing active {active_trade['signal']} trade...")
                ltp = client.get_ltp(symbol=nifty_instrument['symbol'], token=nifty_instrument['token'])

                if ltp is None:
                    log.warning("Could not fetch LTP. Retrying in 10 seconds.")
                    time.sleep(10)
                    continue

                log.info(f"LTP: {ltp}, SL: {active_trade['sl']}, Target: {active_trade['target']}")

                exit_reason = None
                # Check SL/TP conditions
                if active_trade['signal'] == 'BUY':
                    if ltp <= active_trade['sl']: exit_reason = "Stop-Loss"
                    elif ltp >= active_trade['target']: exit_reason = "Target"
                elif active_trade['signal'] == 'SELL':
                    if ltp >= active_trade['sl']: exit_reason = "Stop-Loss"
                    elif ltp <= active_trade['target']: exit_reason = "Target"

                if exit_reason:
                    log.info(f"--- Closing Trade: {exit_reason} Hit ---")
                    closing_signal = 'SELL' if active_trade['signal'] == 'BUY' else 'BUY'

                    if config.PAPER_TRADING:
                        log.info(f"PAPER TRADING: Mock trade closed. Reason: {exit_reason}")
                        active_trade = None
                    else:
                        log.info("REAL TRADING: Placing closing order...")
                        order_id = client.place_order(
                            symbol=nifty_instrument['symbol'], token=nifty_instrument['token'],
                            quantity=config.LOT_SIZE, transaction_type=closing_signal
                        )
                        if order_id:
                            log.info(f"Successfully placed closing order with ID: {order_id}")
                            active_trade = None
                        else:
                            log.error("CRITICAL: Failed to place closing order. Manual intervention may be required.")
                            # In a real bot, you might want to retry or send a notification here.
                            time.sleep(60) # Wait before trying again
                else:
                    # If no exit condition, wait a bit before checking again
                    time.sleep(10)

        except Exception as e:
            log.error(f"An error occurred in the main loop: {e}", exc_info=True)
            time.sleep(60) # Wait a minute before retrying after an error

if __name__ == "__main__":
    run_bot()
