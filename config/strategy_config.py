"""
Configuration for the Bollinger Bands + Stochastic RSI strategy
"""

STRATEGY_CONFIG = {
    # Trading pairs
    'trading_pairs': ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'],
    'timeframes': ['15m', '1h', '4h', '1d'],

    # Bollinger Bands settings
    'boll_window': 20,
    'boll_std': 2.0,

    # EMA settings
    'ema_window': 20,

    # Stochastic RSI settings
    'stoch_window': 14,
    'stoch_smooth_k': 3,
    'stoch_smooth_d': 3,

    # Entry conditions
    'min_confidence': 0.7,  # Minimum confidence score to enter a trade
    'max_spread': 0.002,    # Maximum allowed spread (0.2%)

    # Position sizing
    'position_size': 0.02,  # 2% of account balance per trade
    'max_positions': 3,     # Maximum number of concurrent positions

    # Risk management
    'stop_loss': 0.02,     # 2% stop loss from entry
    'take_profit': 0.03,   # 3% take profit from entry
    'trailing_stop': 0.01,  # 1% trailing stop when in profit

    # Timeframe weights
    'timeframe_weights': {
        '15m': 0.1,
        '1h': 0.3,
        '4h': 0.3,
        '1d': 0.3
    }
}
