import json
import logging
from datetime import datetime
import pandas as pd
import numpy as np
from typing import Dict, Any, List

class PerformanceMetrics:
    def __init__(self):
        self.metrics_file = 'performance_metrics.json'
        self.load_metrics()

    def load_metrics(self):
        try:
            with open(self.metrics_file, 'r') as f:
                self.metrics = json.load(f)
        except FileNotFoundError:
            self.metrics = {
                'total_trades': 0,
                'winning_trades': 0,
                'total_profit': 0,
                'max_drawdown': 0,
                'daily_trades': 0,
                'daily_loss': 0,
                'trade_history': [],
                'last_reset_date': datetime.now().strftime('%Y-%m-%d')
            }
            self.save_metrics()

    def save_metrics(self):
        with open(self.metrics_file, 'w') as f:
            json.dump(self.metrics, f, indent=4)

    def update_trade(self, profit: float, won: bool = False):
        today = datetime.now().strftime('%Y-%m-%d')

        if today != self.metrics['last_reset_date']:
            self.metrics['daily_trades'] = 0
            self.metrics['daily_loss'] = 0
            self.metrics['last_reset_date'] = today

        self.metrics['total_trades'] += 1
        self.metrics['daily_trades'] += 1

        if won:
            self.metrics['winning_trades'] += 1

        self.metrics['total_profit'] += profit
        if profit < 0:
            self.metrics['daily_loss'] += abs(profit)

        self.metrics['trade_history'].append({
            'timestamp': datetime.now().isoformat(),
            'profit': profit,
            'won': won
        })

        self.calculate_metrics()
        self.save_metrics()

    def calculate_metrics(self):
        if self.metrics['total_trades'] > 0:
            self.metrics['win_rate'] = (self.metrics['winning_trades'] / self.metrics['total_trades']) * 100

            if len(self.metrics['trade_history']) > 0:
                profits = [trade['profit'] for trade in self.metrics['trade_history']]
                self.metrics['sharpe_ratio'] = self.calculate_sharpe_ratio(profits)
                self.metrics['max_drawdown'] = self.calculate_max_drawdown(profits)

    @staticmethod
    def calculate_sharpe_ratio(profits: List[float], risk_free_rate: float = 0.02) -> float:
        if len(profits) < 2:
            return 0
        returns = pd.Series(profits)
        excess_returns = returns - (risk_free_rate / 252)
        if excess_returns.std() == 0:
            return 0
        return np.sqrt(252) * (excess_returns.mean() / excess_returns.std())

    @staticmethod
    def calculate_max_drawdown(profits: List[float]) -> float:
        cumulative = np.cumsum(profits)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = running_max - cumulative
        return np.max(drawdown) if len(drawdown) > 0 else 0

    def can_trade(self) -> bool:
        from config.config import CONFIG

        if self.metrics['daily_trades'] >= CONFIG['max_daily_trades']:
            logging.warning('Maximum daily trades reached')
            return False

        if self.metrics['daily_loss'] >= (CONFIG['max_daily_loss_percent'] / 100):
            logging.warning('Maximum daily loss reached')
            return False

        if self.metrics['max_drawdown'] >= CONFIG['max_drawdown_percent']:
            logging.warning('Maximum drawdown reached')
            return False

        return True

def analyze_trading_performance(performance: PerformanceMetrics) -> Dict[str, Any]:
    try:
        metrics = performance.metrics

        # Calculate additional metrics
        win_rate = (metrics['winning_trades'] / metrics['total_trades'] * 100) if metrics['total_trades'] > 0 else 0
        avg_profit = metrics['total_profit'] / metrics['total_trades'] if metrics['total_trades'] > 0 else 0

        # Calculate profit factor
        winning_trades = [t['profit'] for t in metrics['trade_history'] if t['profit'] > 0]
        losing_trades = [t['profit'] for t in metrics['trade_history'] if t['profit'] < 0]

        gross_profit = sum(winning_trades) if winning_trades else 0
        gross_loss = abs(sum(losing_trades)) if losing_trades else 0

        profit_factor = gross_profit / gross_loss if gross_loss != 0 else float('inf')

        return {
            'win_rate': win_rate,
            'avg_profit': avg_profit,
            'profit_factor': profit_factor,
            'total_trades': metrics['total_trades'],
            'total_profit': metrics['total_profit'],
            'max_drawdown': metrics['max_drawdown'],
            'sharpe_ratio': metrics.get('sharpe_ratio', 0)
        }
    except Exception as e:
        logging.error(f"Error analyzing trading performance: {e}")
        raise

def check_risk_limits(performance: PerformanceMetrics) -> Dict[str, bool]:
    from config.config import CONFIG

    metrics = performance.metrics

    return {
        'daily_trades_exceeded': metrics['daily_trades'] >= CONFIG['max_daily_trades'],
        'daily_loss_exceeded': metrics['daily_loss'] >= CONFIG['max_daily_loss_percent'],
        'drawdown_exceeded': metrics['max_drawdown'] >= CONFIG['max_drawdown_percent'],
        'can_trade': performance.can_trade()
    }
