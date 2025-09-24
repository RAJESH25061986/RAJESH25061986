import time
import logging
from datetime import datetime, timedelta, time as dt_time
import app_config as config
from angel_one_client import AngelOneClient
import strategy

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

def run_bot():
    """
    Main function to run the Iron Condor trading bot.
    """
    log.info("--- Starting the Intelligent Iron Condor Bot ---")

    client = AngelOneClient()
    if not client.login():
        log.error("Login failed. Exiting.")
        return

    # Main state machine loop
    while True:
        try:
            # --- 1. Daily Setup Phase ---
            log.info("--- Entering Daily Setup Phase ---")

            # Wait until market is open to get reliable data
            while datetime.now().time() < dt_time(9, 20):
                log.info("Waiting for market to open and settle... (pre-9:20 AM)")
                time.sleep(60)

            # Get previous day's OHLC for pivot calculation
            prev_day_ohlc = client.get_daily_ohlc()
            if not prev_day_ohlc:
                log.error("Could not get previous day OHLC. Retrying in 5 minutes.")
                time.sleep(300)
                continue

            r1, s1 = strategy.calculate_pivots(prev_day_ohlc['high'], prev_day_ohlc['low'], prev_day_ohlc['close'])

            # Get the full option chain for the day
            option_chain = client.get_option_chain(config.TRADING_INSTRUMENT, config.OPTION_EXPIRY)
            if not option_chain:
                log.error("Could not get option chain. Retrying in 5 minutes.")
                time.sleep(300)
                continue

            # --- 2. Entry Phase ---
            log.info("--- Entering Entry Phase: Monitoring for VWAP signal ---")
            active_trade = None
            while active_trade is None:
                now = datetime.now()
                if now.time() > dt_time(15, 15): # Stop looking for trades after 3:15 PM
                    log.info("Past 3:15 PM, stopping entry search for the day.")
                    break

                # First, find the potential legs based on pivots and premiums
                potential_legs = strategy.find_iron_condor_legs(r1, s1, option_chain, client)
                if not potential_legs:
                    log.warning("Could not determine potential legs. Retrying in 5 mins.")
                    time.sleep(300)
                    continue

                # Now check the VWAP condition for the sell legs
                sell_ce = potential_legs['sell_ce']
                sell_pe = potential_legs['sell_pe']

                # Fetch 15-min data for VWAP calculation
                to_date = now.strftime('%Y-%m-%d %H:%M')
                from_date = (now - timedelta(days=1)).strftime('%Y-%m-%d %H:%M')

                ce_hist = client.get_historical_data(sell_ce['token'], config.VWAP_TIMEFRAME, from_date, to_date)
                pe_hist = client.get_historical_data(sell_pe['token'], config.VWAP_TIMEFRAME, from_date, to_date)

                ce_vwap = strategy.calculate_vwap(ce_hist)
                pe_vwap = strategy.calculate_vwap(pe_hist)

                ce_ltp = client.get_ltp(sell_ce['symbol'], sell_ce['token'])
                pe_ltp = client.get_ltp(sell_pe['symbol'], sell_pe['token'])

                if not all([ce_vwap, pe_vwap, ce_ltp, pe_ltp]):
                    log.warning("Missing data for VWAP check. Retrying in 1 minute.")
                    time.sleep(60)
                    continue

                log.info(f"CE: LTP={ce_ltp}, VWAP={ce_vwap} | PE: LTP={pe_ltp}, VWAP={pe_vwap}")

                if ce_ltp < ce_vwap and pe_ltp < pe_vwap:
                    log.info(">>> ENTRY TRIGGERED: Both premiums are below VWAP. <<<")

                    # --- 3. Execution Phase ---
                    total_credit = sell_ce_ltp + sell_pe_ltp - client.get_ltp(potential_legs['buy_ce']['symbol'], potential_legs['buy_ce']['token']) - client.get_ltp(potential_legs['buy_pe']['symbol'], potential_legs['buy_pe']['token'])

                    if config.PAPER_TRADING:
                        log.info("PAPER TRADING: Mocking 4-leg order placement.")
                        active_trade = {'legs': potential_legs, 'credit': total_credit * config.LOT_SIZE}
                    else:
                        log.info("REAL TRADING: Placing 4-leg orders.")
                        # Place orders for all 4 legs
                        # A more robust version would use a basket order if the API supports it
                        sell_ce_id = client.place_order(sell_ce['symbol'], sell_ce['token'], config.LOT_SIZE, 'SELL')
                        buy_ce_id = client.place_order(potential_legs['buy_ce']['symbol'], potential_legs['buy_ce']['token'], config.LOT_SIZE, 'BUY')
                        sell_pe_id = client.place_order(sell_pe['symbol'], sell_pe['token'], config.LOT_SIZE, 'SELL')
                        buy_pe_id = client.place_order(potential_legs['buy_pe']['symbol'], potential_legs['buy_pe']['token'], config.LOT_SIZE, 'BUY')

                        if all([sell_ce_id, buy_ce_id, sell_pe_id, buy_pe_id]):
                            log.info("All 4 orders placed successfully.")
                            active_trade = {'legs': potential_legs, 'credit': total_credit * config.LOT_SIZE}
                        else:
                            log.critical("One or more orders failed to place! Manual intervention required.")
                            # Bot stops here, requires manual check
                            return

                else:
                    log.info("Entry condition not met. Waiting...")
                    time.sleep(60) # Wait 1 minute before re-checking VWAP condition

            # --- 4. Exit Phase ---
            if active_trade:
                log.info("--- Entering Exit Phase: Monitoring active trade P&L ---")

                profit_target = config.ESTIMATED_MARGIN_PER_LOT * (config.PROFIT_PERCENT_MARGIN / 100)
                stop_loss_target = -config.ESTIMATED_MARGIN_PER_LOT * (config.SL_PERCENT_MARGIN / 100)
                log.info(f"P&L Targets: Profit > {profit_target}, Stop-Loss < {stop_loss_target}")

                while True:
                    if datetime.now().time() > dt_time(15, 25):
                        log.info("End of day, closing position.")
                        break # Force exit

                    # Calculate current P&L
                    current_sell_ce_ltp = client.get_ltp(active_trade['legs']['sell_ce']['symbol'], active_trade['legs']['sell_ce']['token'])
                    current_buy_ce_ltp = client.get_ltp(active_trade['legs']['buy_ce']['symbol'], active_trade['legs']['buy_ce']['token'])
                    current_sell_pe_ltp = client.get_ltp(active_trade['legs']['sell_pe']['symbol'], active_trade['legs']['sell_pe']['token'])
                    current_buy_pe_ltp = client.get_ltp(active_trade['legs']['buy_pe']['symbol'], active_trade['legs']['buy_pe']['token'])

                    if not all([current_sell_ce_ltp, current_buy_ce_ltp, current_sell_pe_ltp, current_buy_pe_ltp]):
                        log.warning("Could not fetch all LTPs for P&L calculation. Retrying.")
                        time.sleep(10)
                        continue

                    # The initial credit was SELLs - BUYs. The current value is also SELLs - BUYs.
                    # The P&L is the difference between the credit received and the current credit value.
                    # A positive P&L means the current credit is lower than the initial credit (good for sellers).
                    initial_credit = active_trade['credit']
                    current_value = (current_sell_ce_ltp + current_sell_pe_ltp - current_buy_ce_ltp - current_buy_pe_ltp) * config.LOT_SIZE
                    pnl = initial_credit - current_value

                    log.info(f"Current P&L: {pnl:.2f}")

                    if pnl >= profit_target or pnl <= stop_loss_target:
                        log.info(f"--- EXIT TRIGGERED: P&L at {pnl} ---")
                        # Place closing orders (opposite of entry)
                        if not config.PAPER_TRADING:
                            client.place_order(active_trade['legs']['sell_ce']['symbol'], active_trade['legs']['sell_ce']['token'], config.LOT_SIZE, 'BUY')
                            client.place_order(active_trade['legs']['buy_ce']['symbol'], active_trade['legs']['buy_ce']['token'], config.LOT_SIZE, 'SELL')
                            client.place_order(active_trade['legs']['sell_pe']['symbol'], active_trade['legs']['sell_pe']['token'], config.LOT_SIZE, 'BUY')
                            client.place_order(active_trade['legs']['buy_pe']['symbol'], active_trade['legs']['buy_pe']['token'], config.LOT_SIZE, 'SELL')
                        log.info("All closing orders placed.")
                        break # Exit the exit-monitoring loop

                    time.sleep(15) # Check P&L every 15 seconds

            log.info("--- Trading day finished. Waiting for next day. ---")
            # Wait until the next day to start again
            time.sleep(60 * 60 * 6) # Sleep for 6 hours

        except Exception as e:
            log.error(f"A critical error occurred in the main loop: {e}", exc_info=True)
            log.info("Restarting bot after 5 minutes...")
            time.sleep(300)

if __name__ == "__main__":
    run_bot()
