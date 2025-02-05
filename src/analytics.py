import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dataclasses import dataclass
import json
import os

@dataclass
class TradeMetrics:
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float
    total_pnl: float
    max_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float
    avg_trade_duration: timedelta
    best_trade: float
    worst_trade: float
    avg_profit_per_trade: float
    profit_factor: float
    max_consecutive_wins: int
    max_consecutive_losses: int

class TradingAnalytics:
    def __init__(self, data_dir: str = 'data/analytics'):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)

    def analyze_trades(self, trades: List[Dict[str, Any]]) -> TradeMetrics:
        """Analyze trading performance and generate metrics."""
        try:
            if not trades:
                return self._empty_metrics()

            # Convert trades to DataFrame for analysis
            df = pd.DataFrame(trades)
            df['duration'] = pd.to_datetime(df['exit_time']) - pd.to_datetime(df['entry_time'])

            # Calculate basic metrics
            winning_trades = df[df['pnl'] > 0]
            losing_trades = df[df['pnl'] <= 0]

            total_pnl = df['pnl'].sum()
            win_rate = len(winning_trades) / len(df)

            # Calculate consecutive wins/losses
            consecutive = self._calculate_consecutive_trades(df)

            # Calculate advanced metrics
            metrics = TradeMetrics(
                total_trades=len(df),
                winning_trades=len(winning_trades),
                losing_trades=len(losing_trades),
                win_rate=win_rate,
                profit_factor=abs(winning_trades['pnl'].sum() / losing_trades['pnl'].sum()) if len(losing_trades) > 0 else float('inf'),
                total_pnl=total_pnl,
                max_drawdown=self._calculate_max_drawdown(df),
                sharpe_ratio=self._calculate_sharpe_ratio(df['pnl']),
                sortino_ratio=self._calculate_sortino_ratio(df['pnl']),
                avg_trade_duration=df['duration'].mean(),
                best_trade=df['pnl'].max(),
                worst_trade=df['pnl'].min(),
                avg_profit_per_trade=df['pnl'].mean(),
                profit_factor=abs(winning_trades['pnl'].sum() / losing_trades['pnl'].sum()) if len(losing_trades) > 0 else float('inf'),
                max_consecutive_wins=consecutive['max_wins'],
                max_consecutive_losses=consecutive['max_losses']
            )

            # Save metrics
            self._save_metrics(metrics)

            return metrics

        except Exception as e:
            logging.error(f"Error analyzing trades: {e}")
            return self._empty_metrics()

    def generate_performance_report(self, trades: List[Dict[str, Any]],
                                  market_data: pd.DataFrame) -> None:
        """Generate comprehensive performance report with visualizations."""
        try:
            metrics = self.analyze_trades(trades)

            # Create report directory
            report_dir = os.path.join(self.data_dir, 'reports')
            os.makedirs(report_dir, exist_ok=True)

            # Generate plots
            self._plot_equity_curve(trades, report_dir)
            self._plot_drawdown(trades, report_dir)
            self._plot_monthly_returns(trades, report_dir)
            self._plot_trade_distribution(trades, report_dir)

            # Save report as HTML
            self._generate_html_report(metrics, report_dir)

        except Exception as e:
            logging.error(f"Error generating performance report: {e}")

    def _calculate_consecutive_trades(self, df: pd.DataFrame) -> Dict[str, int]:
        """Calculate maximum consecutive winning and losing trades."""
        wins = losses = max_wins = max_losses = current_wins = current_losses = 0

        for pnl in df['pnl']:
            if pnl > 0:
                current_wins += 1
                current_losses = 0
                max_wins = max(max_wins, current_wins)
            else:
                current_losses += 1
                current_wins = 0
                max_losses = max(max_losses, current_losses)

        return {'max_wins': max_wins, 'max_losses': max_losses}

    def _calculate_max_drawdown(self, df: pd.DataFrame) -> float:
        """Calculate maximum drawdown from trade history."""
        cumulative = df['pnl'].cumsum()
        rolling_max = cumulative.expanding().max()
        drawdowns = (cumulative - rolling_max) / rolling_max
        return abs(drawdowns.min()) if len(drawdowns) > 0 else 0

    def _calculate_sharpe_ratio(self, returns: pd.Series, risk_free_rate: float = 0.02) -> float:
        """Calculate annualized Sharpe ratio."""
        if len(returns) < 2:
            return 0
        excess_returns = returns - (risk_free_rate / 252)  # Daily risk-free rate
        return np.sqrt(252) * (excess_returns.mean() / excess_returns.std()) if excess_returns.std() != 0 else 0

    def _calculate_sortino_ratio(self, returns: pd.Series, risk_free_rate: float = 0.02) -> float:
        """Calculate Sortino ratio using only negative returns for risk."""
        if len(returns) < 2:
            return 0
        excess_returns = returns - (risk_free_rate / 252)
        downside_returns = excess_returns[excess_returns < 0]
        downside_std = downside_returns.std()
        return np.sqrt(252) * (excess_returns.mean() / downside_std) if downside_std != 0 else 0

    def _plot_equity_curve(self, trades: List[Dict[str, Any]], report_dir: str) -> None:
        """Plot equity curve with drawdown overlay."""
        df = pd.DataFrame(trades)
        cumulative = df['pnl'].cumsum()

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df.index,
            y=cumulative,
            name='Equity Curve',
            line=dict(color='blue')
        ))

        fig.update_layout(
            title='Equity Curve',
            xaxis_title='Trade Number',
            yaxis_title='Cumulative P&L'
        )

        fig.write_html(os.path.join(report_dir, 'equity_curve.html'))

    def _plot_drawdown(self, trades: List[Dict[str, Any]], report_dir: str) -> None:
        """Plot drawdown chart."""
        df = pd.DataFrame(trades)
        cumulative = df['pnl'].cumsum()
        rolling_max = cumulative.expanding().max()
        drawdown = (cumulative - rolling_max) / rolling_max * 100

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df.index,
            y=drawdown,
            name='Drawdown',
            fill='tozeroy',
            line=dict(color='red')
        ))

        fig.update_layout(
            title='Drawdown Analysis',
            xaxis_title='Trade Number',
            yaxis_title='Drawdown %'
        )

        fig.write_html(os.path.join(report_dir, 'drawdown.html'))

    def _plot_monthly_returns(self, trades: List[Dict[str, Any]], report_dir: str) -> None:
        """Plot monthly returns heatmap."""
        df = pd.DataFrame(trades)
        df['date'] = pd.to_datetime(df['exit_time'])
        monthly_returns = df.groupby([df['date'].dt.year, df['date'].dt.month])['pnl'].sum()

        # Create heatmap data
        years = sorted(df['date'].dt.year.unique())
        months = range(1, 13)
        data = np.zeros((len(years), 12))

        for i, year in enumerate(years):
            for j, month in enumerate(months):
                if (year, month) in monthly_returns.index:
                    data[i, j] = monthly_returns[year, month]

        fig = go.Figure(data=go.Heatmap(
            z=data,
            x=['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
            y=years,
            colorscale='RdYlGn'
        ))

        fig.update_layout(title='Monthly Returns Heatmap')
        fig.write_html(os.path.join(report_dir, 'monthly_returns.html'))

    def _plot_trade_distribution(self, trades: List[Dict[str, Any]], report_dir: str) -> None:
        """Plot trade P&L distribution."""
        df = pd.DataFrame(trades)

        fig = go.Figure()
        fig.add_trace(go.Histogram(
            x=df['pnl'],
            nbinsx=50,
            name='P&L Distribution'
        ))

        fig.update_layout(
            title='Trade P&L Distribution',
            xaxis_title='P&L',
            yaxis_title='Frequency'
        )

        fig.write_html(os.path.join(report_dir, 'pnl_distribution.html'))

    def _generate_html_report(self, metrics: TradeMetrics, report_dir: str) -> None:
        """Generate HTML report with all metrics and plots."""
        html_content = f"""
        <html>
        <head>
            <title>Trading Performance Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .metric {{ margin: 10px 0; }}
                .positive {{ color: green; }}
                .negative {{ color: red; }}
            </style>
        </head>
        <body>
            <h1>Trading Performance Report</h1>

            <h2>Key Metrics</h2>
            <div class="metric">Total Trades: {metrics.total_trades}</div>
            <div class="metric">Win Rate: {metrics.win_rate:.2%}</div>
            <div class="metric">Profit Factor: {metrics.profit_factor:.2f}</div>
            <div class="metric">Total P&L: <span class="{'positive' if metrics.total_pnl > 0 else 'negative'}">${metrics.total_pnl:,.2f}</span></div>
            <div class="metric">Max Drawdown: {metrics.max_drawdown:.2%}</div>
            <div class="metric">Sharpe Ratio: {metrics.sharpe_ratio:.2f}</div>
            <div class="metric">Sortino Ratio: {metrics.sortino_ratio:.2f}</div>

            <h2>Trade Statistics</h2>
            <div class="metric">Best Trade: ${metrics.best_trade:,.2f}</div>
            <div class="metric">Worst Trade: ${metrics.worst_trade:,.2f}</div>
            <div class="metric">Average Profit per Trade: ${metrics.avg_profit_per_trade:,.2f}</div>
            <div class="metric">Max Consecutive Wins: {metrics.max_consecutive_wins}</div>
            <div class="metric">Max Consecutive Losses: {metrics.max_consecutive_losses}</div>

            <h2>Charts</h2>
            <iframe src="equity_curve.html" width="100%" height="600px"></iframe>
            <iframe src="drawdown.html" width="100%" height="600px"></iframe>
            <iframe src="monthly_returns.html" width="100%" height="600px"></iframe>
            <iframe src="pnl_distribution.html" width="100%" height="600px"></iframe>
        </body>
        </html>
        """

        with open(os.path.join(report_dir, 'report.html'), 'w') as f:
            f.write(html_content)

    def _empty_metrics(self) -> TradeMetrics:
        """Return empty metrics when no trades are available."""
        return TradeMetrics(
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            profit_factor=0.0,
            total_pnl=0.0,
            max_drawdown=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            avg_trade_duration=timedelta(0),
            best_trade=0.0,
            worst_trade=0.0,
            avg_profit_per_trade=0.0,
            profit_factor=0.0,
            max_consecutive_wins=0,
            max_consecutive_losses=0
        )

    def _save_metrics(self, metrics: TradeMetrics) -> None:
        """Save metrics to JSON file."""
        metrics_dict = {
            'timestamp': datetime.now().isoformat(),
            'metrics': {
                'total_trades': metrics.total_trades,
                'winning_trades': metrics.winning_trades,
                'losing_trades': metrics.losing_trades,
                'win_rate': metrics.win_rate,
                'profit_factor': metrics.profit_factor,
                'total_pnl': metrics.total_pnl,
                'max_drawdown': metrics.max_drawdown,
                'sharpe_ratio': metrics.sharpe_ratio,
                'sortino_ratio': metrics.sortino_ratio,
                'avg_trade_duration': str(metrics.avg_trade_duration),
                'best_trade': metrics.best_trade,
                'worst_trade': metrics.worst_trade,
                'avg_profit_per_trade': metrics.avg_profit_per_trade,
                'max_consecutive_wins': metrics.max_consecutive_wins,
                'max_consecutive_losses': metrics.max_consecutive_losses
            }
        }

        with open(os.path.join(self.data_dir, 'metrics.json'), 'w') as f:
            json.dump(metrics_dict, f, indent=4)
