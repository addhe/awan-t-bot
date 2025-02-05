import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

class PerformanceMetrics:
    def __init__(self):
        self.trades: List[Dict[str, Any]] = []
        self.daily_pnl: Dict[str, float] = {}
        self.consecutive_losses = 0
        self.total_trades = 0
        self.winning_trades = 0
        self.start_balance = 0
        self.current_balance = 0
        self.max_balance = 0

    def update_trade(self, pnl: float, closed: bool = True) -> None:
        """
        Update performance metrics with a new trade.

        Args:
            pnl: Profit/Loss amount
            closed: Whether the trade is closed
        """
        try:
            current_time = datetime.now()
            date_key = current_time.strftime('%Y-%m-%d')

            trade_info = {
                'timestamp': current_time,
                'pnl': pnl,
                'closed': closed
            }

            self.trades.append(trade_info)

            # Update daily PnL
            if date_key in self.daily_pnl:
                self.daily_pnl[date_key] += pnl
            else:
                self.daily_pnl[date_key] = pnl

            # Update consecutive losses
            if pnl < 0:
                self.consecutive_losses += 1
            else:
                self.consecutive_losses = 0

            # Update trade counts
            if closed:
                self.total_trades += 1
                if pnl > 0:
                    self.winning_trades += 1

        except Exception as e:
            logging.error(f"Error updating performance metrics: {e}")

    def daily_loss_percentage(self) -> float:
        """Calculate today's loss percentage."""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            if today in self.daily_pnl:
                daily_loss = self.daily_pnl[today]
                return abs(daily_loss) / self.start_balance * 100 if daily_loss < 0 else 0
            return 0

        except Exception as e:
            logging.error(f"Error calculating daily loss percentage: {e}")
            return 0

    def max_drawdown(self) -> float:
        """Calculate maximum drawdown percentage."""
        try:
            if not self.trades:
                return 0

            balances = [self.start_balance]
            current_balance = self.start_balance

            for trade in self.trades:
                current_balance += trade['pnl']
                balances.append(current_balance)

            cummax = pd.Series(balances).expanding().max()
            drawdown = (cummax - balances) / cummax * 100
            return drawdown.max()

        except Exception as e:
            logging.error(f"Error calculating max drawdown: {e}")
            return 0

    def win_rate(self) -> float:
        """Calculate win rate percentage."""
        try:
            if self.total_trades == 0:
                return 0
            return (self.winning_trades / self.total_trades) * 100

        except Exception as e:
            logging.error(f"Error calculating win rate: {e}")
            return 0

    def can_trade(self) -> bool:
        """Check if we can make new trades based on performance metrics."""
        try:
            # Check daily loss limit
            if self.daily_loss_percentage() >= 3:  # 3% daily loss limit
                logging.warning("Daily loss limit reached")
                return False

            # Check drawdown limit
            if self.max_drawdown() >= 5:  # 5% max drawdown
                logging.warning("Max drawdown limit reached")
                return False

            # Check consecutive losses
            if self.consecutive_losses >= 3:
                logging.warning("Too many consecutive losses")
                return False

            return True

        except Exception as e:
            logging.error(f"Error checking if can trade: {e}")
            return False

def analyze_trading_performance(metrics: PerformanceMetrics) -> Dict[str, Any]:
    """
    Analyze trading performance metrics.

    Args:
        metrics: PerformanceMetrics instance

    Returns:
        Dict containing performance analysis
    """
    try:
        return {
            'total_trades': metrics.total_trades,
            'win_rate': metrics.win_rate(),
            'max_drawdown': metrics.max_drawdown(),
            'daily_loss_pct': metrics.daily_loss_percentage(),
            'consecutive_losses': metrics.consecutive_losses
        }

    except Exception as e:
        logging.error(f"Error analyzing performance: {e}")
        return {}

def check_risk_limits(metrics: PerformanceMetrics) -> bool:
    """
    Check if any risk limits have been exceeded.

    Args:
        metrics: PerformanceMetrics instance

    Returns:
        bool: True if within limits, False if exceeded
    """
    try:
        # Check daily loss
        if metrics.daily_loss_percentage() > 3:
            logging.warning("Daily loss limit exceeded")
            return False

        # Check drawdown
        if metrics.max_drawdown() > 5:
            logging.warning("Maximum drawdown exceeded")
            return False

        # Check win rate
        if metrics.total_trades > 10 and metrics.win_rate() < 40:
            logging.warning("Win rate below threshold")
            return False

        return True

    except Exception as e:
        logging.error(f"Error checking risk limits: {e}")
        return False
