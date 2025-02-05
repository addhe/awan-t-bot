import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
import plotly.graph_objects as go
from plotly.subplots import make_subplots

@dataclass
class BacktestTrade:
    entry_time: datetime
    exit_time: Optional[datetime]
    side: str
    entry_price: float
    exit_price: Optional[float]
    size: float
    pnl: float = 0.0
    status: str = 'open'
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

class Backtester:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.trades: List[BacktestTrade] = []
        self.current_trade: Optional[BacktestTrade] = None
        self.balance = config.get('initial_balance', 10000)
        self.peak_balance = self.balance
        self.max_drawdown = 0.0

    def run_backtest(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Run backtest on historical data."""
        try:
            results = []
            running_balance = [self.balance]

            for i in range(1, len(df)):
                current_row = df.iloc[i]
                prev_row = df.iloc[i-1]

                # Update current trade if exists
                if self.current_trade:
                    self._update_trade(current_row)

                # Check for new trade signals
                signal = self._generate_signal(current_row, prev_row)
                if signal and not self.current_trade:
                    self._open_trade(current_row, signal)

                # Track balance
                running_balance.append(self.balance)

                # Update max drawdown
                self._update_drawdown(running_balance[-1])

            # Close any remaining trades
            if self.current_trade:
                self._close_trade(df.iloc[-1], 'end_of_period')

            return self._generate_backtest_report(df, running_balance)

        except Exception as e:
            logging.error(f"Backtest error: {e}")
            raise

    def _generate_signal(self, row: pd.Series, prev_row: pd.Series) -> Optional[str]:
        """Generate trading signals based on indicators."""
        try:
            # Trend following strategy
            trend_up = row['sma_20'] > row['sma_50']
            momentum_up = row['rsi'] > 50
            macd_cross = (row['macd'] > row['macd_signal']) and (prev_row['macd'] <= prev_row['macd_signal'])

            trend_down = row['sma_20'] < row['sma_50']
            momentum_down = row['rsi'] < 50
            macd_cross_down = (row['macd'] < row['macd_signal']) and (prev_row['macd'] >= prev_row['macd_signal'])

            if trend_up and momentum_up and macd_cross:
                return 'buy'
            elif trend_down and momentum_down and macd_cross_down:
                return 'sell'

            return None

        except Exception as e:
            logging.error(f"Signal generation error: {e}")
            return None

    def _open_trade(self, row: pd.Series, side: str) -> None:
        """Open a new trade."""
        try:
            # Calculate position size (1% risk per trade)
            risk_amount = self.balance * 0.01
            atr = row['atr']
            size = risk_amount / atr

            # Calculate stop loss and take profit
            if side == 'buy':
                stop_loss = row['close'] - (2 * atr)
                take_profit = row['close'] + (3 * atr)
            else:
                stop_loss = row['close'] + (2 * atr)
                take_profit = row['close'] - (3 * atr)

            self.current_trade = BacktestTrade(
                entry_time=row.name,
                exit_time=None,
                side=side,
                entry_price=row['close'],
                exit_price=None,
                size=size,
                stop_loss=stop_loss,
                take_profit=take_profit
            )

        except Exception as e:
            logging.error(f"Error opening trade: {e}")

    def _update_trade(self, row: pd.Series) -> None:
        """Update current trade status."""
        if not self.current_trade:
            return

        # Check stop loss and take profit
        if self.current_trade.side == 'buy':
            if row['low'] <= self.current_trade.stop_loss:
                self._close_trade(row, 'stop_loss')
            elif row['high'] >= self.current_trade.take_profit:
                self._close_trade(row, 'take_profit')
        else:
            if row['high'] >= self.current_trade.stop_loss:
                self._close_trade(row, 'stop_loss')
            elif row['low'] <= self.current_trade.take_profit:
                self._close_trade(row, 'take_profit')

    def _close_trade(self, row: pd.Series, reason: str) -> None:
        """Close current trade."""
        if not self.current_trade:
            return

        self.current_trade.exit_time = row.name
        self.current_trade.exit_price = row['close']
        self.current_trade.status = reason

        # Calculate PnL
        price_diff = self.current_trade.exit_price - self.current_trade.entry_price
        if self.current_trade.side == 'sell':
            price_diff = -price_diff

        self.current_trade.pnl = price_diff * self.current_trade.size

        # Update balance
        self.balance += self.current_trade.pnl

        # Store trade
        self.trades.append(self.current_trade)
        self.current_trade = None

    def _update_drawdown(self, current_balance: float) -> None:
        """Update maximum drawdown."""
        self.peak_balance = max(self.peak_balance, current_balance)
        current_drawdown = (self.peak_balance - current_balance) / self.peak_balance
        self.max_drawdown = max(self.max_drawdown, current_drawdown)

    def _generate_backtest_report(self, df: pd.DataFrame, balance_history: List[float]) -> Dict[str, Any]:
        """Generate comprehensive backtest report."""
        winning_trades = [t for t in self.trades if t.pnl > 0]
        losing_trades = [t for t in self.trades if t.pnl <= 0]

        total_pnl = sum(t.pnl for t in self.trades)
        win_rate = len(winning_trades) / len(self.trades) if self.trades else 0

        avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.pnl for t in losing_trades]) if losing_trades else 0
        profit_factor = abs(sum(t.pnl for t in winning_trades) / sum(t.pnl for t in losing_trades)) if losing_trades else float('inf')

        return {
            'total_trades': len(self.trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'total_pnl': total_pnl,
            'max_drawdown': self.max_drawdown,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'final_balance': self.balance,
            'return_pct': (self.balance - self.config['initial_balance']) / self.config['initial_balance'] * 100,
            'sharpe_ratio': self._calculate_sharpe_ratio(balance_history),
            'trades': self.trades
        }

    def _calculate_sharpe_ratio(self, balance_history: List[float], risk_free_rate: float = 0.02) -> float:
        """Calculate Sharpe ratio."""
        returns = pd.Series(balance_history).pct_change().dropna()
        excess_returns = returns - (risk_free_rate / 252)  # Daily risk-free rate
        if len(excess_returns) < 2:
            return 0
        return np.sqrt(252) * (excess_returns.mean() / excess_returns.std())

    def plot_results(self, df: pd.DataFrame, balance_history: List[float]) -> None:
        """Generate interactive plots of backtest results."""
        fig = make_subplots(rows=3, cols=1, shared_xaxis=True,
                          subplot_titles=('Price and Trades', 'Balance', 'Indicators'),
                          vertical_spacing=0.05, row_heights=[0.5, 0.25, 0.25])

        # Price chart with trades
        fig.add_trace(go.Candlestick(
            x=df.index,
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name='Price'
        ), row=1, col=1)

        # Add trades
        for trade in self.trades:
            color = 'green' if trade.pnl > 0 else 'red'
            fig.add_trace(go.Scatter(
                x=[trade.entry_time, trade.exit_time],
                y=[trade.entry_price, trade.exit_price],
                mode='markers+lines',
                line=dict(color=color),
                name=f'{trade.side.upper()} ({trade.status})'
            ), row=1, col=1)

        # Balance chart
        fig.add_trace(go.Scatter(
            x=df.index,
            y=balance_history,
            name='Balance'
        ), row=2, col=1)

        # Indicators
        fig.add_trace(go.Scatter(
            x=df.index,
            y=df['rsi'],
            name='RSI'
        ), row=3, col=1)

        fig.update_layout(
            title='Backtest Results',
            xaxis_rangeslider_visible=False,
            height=1000
        )

        # Save plot
        fig.write_html('backtest_results.html')
