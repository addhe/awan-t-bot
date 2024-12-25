import logging

def confirm_signal(df, side, current_idx):
    try:
        # Price action confirmation
        last_candles = 3
        if side == 'buy':
            higher_lows = all(
                df['low'].iloc[i] > df['low'].iloc[i-1]
                for i in range(current_idx-last_candles+1, current_idx+1)
            )
            return higher_lows
        else:
            lower_highs = all(
                df['high'].iloc[i] < df['high'].iloc[i-1]
                for i in range(current_idx-last_candles+1, current_idx+1)
            )
            return lower_highs
    except Exception as e:
        logging.error(f"Error confirming signal: {e}")
        return False