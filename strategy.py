import pandas as pd
import pandas_ta as ta
import logging
import app_config as config

log = logging.getLogger(__name__)

def check_strategy_signal(df: pd.DataFrame):
    """
    Checks for a trading signal based on the Supertrend and RSI strategy.

    :param df: A pandas DataFrame containing the 5-minute candle data for Nifty.
               It must have 'open', 'high', 'low', 'close', 'volume' columns.
    :return: A tuple containing (signal, stop_loss).
             signal can be 'BUY', 'SELL', or 'HOLD'.
             stop_loss is the calculated stop-loss price for the trade, or None.
    """
    if df.empty or len(df) < config.SUPERTREND_PERIOD:
        log.warning("DataFrame is too small to calculate indicators. Holding.")
        return 'HOLD', None

    # Calculate indicators using pandas-ta
    # The 'supertrend' function returns a DataFrame with the Supertrend line and direction
    supertrend = ta.supertrend(df['high'], df['low'], df['close'], length=config.SUPERTREND_PERIOD, multiplier=config.SUPERTREND_MULTIPLIER)
    # The 'rsi' function returns a Series with RSI values
    rsi = ta.rsi(df['close'], length=config.RSI_PERIOD)

    # Append indicators to the DataFrame for easy access
    df['supertrend_direction'] = supertrend[f'SUPERTd_{config.SUPERTREND_PERIOD}_{config.SUPERTREND_MULTIPLIER}.0']
    df['rsi'] = rsi

    # We look at the most recently completed candle, which is the second to last row (-2)
    # The last row (-1) is the current, incomplete candle.
    last_candle = df.iloc[-2]
    # The candle before the signal candle, used for stop-loss calculation
    prev_candle = df.iloc[-3]

    # --- Buy Signal Conditions ---
    is_green_candle = last_candle['close'] > last_candle['open']
    is_supertrend_buy = last_candle['supertrend_direction'] == 1
    is_rsi_bullish = last_candle['rsi'] > config.RSI_MIDLINE

    if is_green_candle and is_supertrend_buy and is_rsi_bullish:
        log.info("BUY SIGNAL DETECTED.")
        stop_loss = prev_candle['low']
        log.info(f"Calculated Stop-Loss: {stop_loss}")
        return 'BUY', stop_loss

    # --- Sell Signal Conditions ---
    is_red_candle = last_candle['close'] < last_candle['open']
    is_supertrend_sell = last_candle['supertrend_direction'] == -1
    is_rsi_bearish = last_candle['rsi'] < config.RSI_MIDLINE

    if is_red_candle and is_supertrend_sell and is_rsi_bearish:
        log.info("SELL SIGNAL DETECTED.")
        stop_loss = prev_candle['high']
        log.info(f"Calculated Stop-Loss: {stop_loss}")
        return 'SELL', stop_loss

    # --- No Signal ---
    log.debug("No signal detected on the last candle. Holding.")
    return 'HOLD', None

# Example usage for testing
if __name__ == '__main__':
    # Create a dummy DataFrame to test the logic
    # In a real scenario, this data would come from the Angel One client
    log.info("--- Running Strategy Logic Test ---")
    data = {
        'open':  [18000, 18010, 18020, 18030, 18040, 18050, 18060, 18070, 18080, 18090, 18100, 18110, 18120, 18130, 18100],
        'high':  [18025, 18035, 18045, 18055, 18065, 18075, 18085, 18095, 18105, 18115, 18125, 18135, 18145, 18155, 18120],
        'low':   [17990, 18000, 18010, 18020, 18030, 18040, 18050, 18060, 18070, 18080, 18090, 18100, 18110, 18120, 18090],
        'close': [18015, 18025, 18035, 18045, 18055, 18065, 18075, 18085, 18095, 18105, 18115, 18125, 18135, 18145, 18110], # Red signal candle
        'volume':[100] * 15
    }
    dummy_df = pd.DataFrame(data)

    # Manually set RSI and Supertrend for a clear SELL signal on the second to last candle
    dummy_df['rsi'] = 60 # Default to bullish
    dummy_df.loc[dummy_df.index[-2], 'rsi'] = 45 # Make signal candle bearish

    dummy_df['supertrend_direction'] = 1 # Default to buy
    dummy_df.loc[dummy_df.index[-2], 'supertrend_direction'] = -1 # Make signal candle sell

    signal, sl = check_strategy_signal(dummy_df)
    log.info(f"Test Result -> Signal: {signal}, Stop-Loss: {sl}")
    # Expected: SELL, 18145.0

    # Now test a BUY signal
    dummy_df.loc[dummy_df.index[-2], 'close'] = 18150 # Make it a green candle
    dummy_df.loc[dummy_df.index[-2], 'rsi'] = 55
    dummy_df.loc[dummy_df.index[-2], 'supertrend_direction'] = 1

    signal, sl = check_strategy_signal(dummy_df)
    log.info(f"Test Result -> Signal: {signal}, Stop-Loss: {sl}")
    # Expected: BUY, 18120.0
