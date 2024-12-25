CONFIG = {
    'symbol': 'BTC/USDT',
    'max_positions': 3,
    'profit_target_percent': 0.015,  # 1.5%
    'fee_rate': 0.0004,
    'trailing_stop_percent': 0.003,  # 0.3%
    'partial_tp_1': 0.7,
    'partial_tp_2': 0.3,
    'tp1_target': 0.01,  # 1%
    'tp2_target': 0.02,  # 2%
    'stop_loss_percent': 0.015,  # 1.5%
    'timeframe': '5m',
    'ema_short_period': 8,
    'ema_long_period': 21,
    'risk_percentage': 1,  # 2% dari balance
    'leverage': 2,
    'min_balance': 90,  # Turunkan ke $10
    'funding_rate_threshold': 0.0030,
    # New config parameters
    'max_daily_trades': 10,  # Kurangi jumlah trade
    'max_daily_loss_percent': 5,  # Turunkan max loss
    'max_drawdown_percent': 10,  # Turunkan max drawdown
    'atr_period': 14,
    'max_volatility_threshold': 0.05,
    'min_volume_usdt': 10000,  # Turunkan ke 10,000 USDT
    'excluded_hours': [0, 1, 23],
    'max_atr_threshold': 0.5,
    'vwap_period': 20,
    'initial_profit_for_trailing_stop': 0.01,  # 1% profit before trailing stop becomes active
    'trailing_distance_pct': 0.005,
    'high_volatility_threshold': 0.05,      # 5% daily volatility considered high
    'low_volatility_threshold': 0.02,       # 2% daily volatility considered low
    'high_volatility_adjustment': 0.3,      # Reduce position size by 30% when high volatility
    'low_volatility_adjustment': 0.2,       # Increase position size by 20% when low volatility
    'max_loss_per_position': 2,  # 2% of total balance
    're_evaluate_volatility_threshold': 0.06,  # High volatility threshold 6%
}