"""
Configuration for the Bollinger Bands + Stochastic RSI strategy
"""

STRATEGY_CONFIG = {
    # Trading pairs
    "trading_pairs": ["BTC/USDT", "ETH/USDT", "SOL/USDT"],
    "timeframes": ["15m", "1h", "4h", "1d"],
    # Bollinger Bands settings
    "boll_window": 20,
    "boll_std": 2.0,
    # EMA settings
    "ema_window": 20,
    # Stochastic RSI settings
    "stoch_window": 14,
    "stoch_smooth_k": 3,
    "stoch_smooth_d": 3,
    # Entry conditions
    "max_spread": 0.002,  # Maximum allowed spread (0.2%)
    # Position sizing
    "position_size": 0.02,  # 2% of account balance per trade
    "max_positions": 3,  # Maximum number of concurrent positions
    # Risk management
    "disable_stop_loss": True,  # Disable stop loss to avoid premature exits
    "take_profit_pct": 0.10,  # 10% take profit from entry (higher target)
    "stop_loss_pct": 0.05,  # 5% stop loss from entry (not used when disabled)
    "trailing_stop_pct": 0.03,  # 3% trailing stop when in profit
    "min_profit_pct": 0.03,  # Minimum 3% profit before allowing exit
    "hold_time_minutes": 30,  # Minimum hold time in minutes before considering exit
    # Timeframe weights
    "timeframe_weights": {"15m": 0.1, "1h": 0.3, "4h": 0.3, "1d": 0.3},
}
