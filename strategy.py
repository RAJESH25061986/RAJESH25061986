import pandas as pd
import pandas_ta as ta
import logging
import app_config as config

log = logging.getLogger(__name__)

def calculate_pivots(prev_high, prev_low, prev_close):
    """
    Calculates the classic daily pivot points.
    """
    pivot = (prev_high + prev_low + prev_close) / 3
    s1 = (2 * pivot) - prev_high
    r1 = (2 * pivot) - prev_low
    log.info(f"Calculated Pivots: R1={r1}, S1={s1}")
    return r1, s1

def find_iron_condor_legs(r1, s1, option_chain, client):
    """
    Finds the four legs for an Iron Condor based on pivot points and hedging rules.
    """
    log.info("Finding Iron Condor legs...")

    # --- 1. Find Strikes to SELL ---
    # Find the call strike closest to R1 (but above it)
    potential_sell_calls = [c for c in option_chain['calls'] if c['strike'] >= r1]
    if not potential_sell_calls:
        log.error("No suitable Call options found above R1.")
        return None
    sell_ce = min(potential_sell_calls, key=lambda x: x['strike'])

    # Find the put strike closest to S1 (but below it)
    potential_sell_puts = [p for p in option_chain['puts'] if p['strike'] <= s1]
    if not potential_sell_puts:
        log.error("No suitable Put options found below S1.")
        return None
    sell_pe = max(potential_sell_puts, key=lambda x: x['strike'])

    log.info(f"Selected SELL legs: CE at {sell_ce['strike']}, PE at {sell_pe['strike']}")

    # --- 2. Find Strikes to BUY (Hedges) ---
    # Get live premiums of the selected sell legs
    sell_ce_ltp = client.get_ltp(symbol=sell_ce['symbol'], token=sell_ce['token'])
    sell_pe_ltp = client.get_ltp(symbol=sell_pe['symbol'], token=sell_pe['token'])

    if not all([sell_ce_ltp, sell_pe_ltp]):
        log.error("Could not fetch premiums for sell legs. Cannot find hedges.")
        return None

    # --- Find Call Hedge ---
    target_ce_hedge_premium = sell_ce_ltp * config.HEDGE_PREMIUM_RATIO
    max_ce_strike = sell_ce['strike'] * (1 + config.HEDGE_STRIKE_DISTANCE_PERCENT / 100)
    potential_buy_calls = [c for c in option_chain['calls'] if sell_ce['strike'] < c['strike'] <= max_ce_strike]

    # Find the best call hedge by checking premium
    best_buy_ce = None
    min_ce_premium_diff = float('inf')
    for option in potential_buy_calls:
        ltp = client.get_ltp(symbol=option['symbol'], token=option['token'])
        if ltp:
            diff = abs(ltp - target_ce_hedge_premium)
            if diff < min_ce_premium_diff:
                min_ce_premium_diff = diff
                best_buy_ce = option

    # --- Find Put Hedge ---
    target_pe_hedge_premium = sell_pe_ltp * config.HEDGE_PREMIUM_RATIO
    min_pe_strike = sell_pe['strike'] * (1 - config.HEDGE_STRIKE_DISTANCE_PERCENT / 100)
    potential_buy_puts = [p for p in option_chain['puts'] if min_pe_strike <= p['strike'] < sell_pe['strike']]

    best_buy_pe = None
    min_pe_premium_diff = float('inf')
    for option in potential_buy_puts:
        ltp = client.get_ltp(symbol=option['symbol'], token=option['token'])
        if ltp:
            diff = abs(ltp - target_pe_hedge_premium)
            if diff < min_pe_premium_diff:
                min_pe_premium_diff = diff
                best_buy_pe = option

    if not all([best_buy_ce, best_buy_pe]):
        log.error("Could not find suitable hedge legs based on premium rules.")
        return None

    log.info(f"Selected BUY legs: CE at {best_buy_ce['strike']}, PE at {best_buy_pe['strike']}")

    return {
        'sell_ce': sell_ce,
        'buy_ce': best_buy_ce,
        'sell_pe': sell_pe,
        'buy_pe': best_buy_pe
    }

def calculate_vwap(df):
    """
    Calculates VWAP for a given DataFrame.
    Requires 'high', 'low', 'close', 'volume' columns.
    """
    if df is None or df.empty:
        return None
    # Calculate VWAP using pandas-ta. It appends a column like 'VWAP_D' or 'VWAP_14_D'
    df.ta.vwap(append=True)
    # Find the vwap column dynamically to avoid key errors
    vwap_col = next((col for col in df.columns if 'VWAP' in col), None)
    if vwap_col:
        return df[vwap_col].iloc[-1]
    else:
        log.error("VWAP column not found after calculation.")
        return None
