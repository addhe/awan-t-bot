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
    
    # Auto-reinvest configuration
    "auto_reinvest": {
        "enabled": True,
        "min_profit_to_reinvest": 0.02,  # Minimum 2% profit before considering reinvestment
        "reinvest_percentage": 0.5,     # Reinvest 50% of profits
        "max_reinvest_times": 3         # Maximum number of times to reinvest profits
    },
    
    # DCA (Dollar Cost Averaging) configuration
    "dca": {
        "enabled": True,
        "price_drop_percentage": 0.03,  # 3% price drop triggers DCA
        "max_dca_levels": 3,           # Maximum DCA levels
        "dca_multiplier": 1.5,         # Each DCA level increases position size by 50%
        "min_balance_required": 0.1    # Minimum 10% balance required for DCA
    },
    
    # Take profit levels configuration (scaled selling)
    "take_profit_levels": [
        {"percentage": 0.3, "profit_target": 0.05},  # 30% at 5% profit
        {"percentage": 0.3, "profit_target": 0.10},  # 30% at 10% profit
        {"percentage": 0.4, "profit_target": 0.20}   # 40% at 20% profit
    ],
}
