"""
Bot status monitoring and reporting
"""
import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Any
from pathlib import Path

logger = logging.getLogger(__name__)

class BotStatusMonitor:
    def __init__(self, status_dir: str = "status"):
        self.status_dir = status_dir
        self.status_file = os.path.join(status_dir, "bot_status.json")
        self.trades_file = os.path.join(status_dir, "active_trades.json")
        self._ensure_status_dir()

    def _ensure_status_dir(self):
        """Ensure status directory exists"""
        Path(self.status_dir).mkdir(parents=True, exist_ok=True)

    def update_bot_status(self, status: Dict[str, Any]):
        """Update bot status"""
        try:
            status['last_updated'] = datetime.now().isoformat()
            with open(self.status_file, 'w') as f:
                json.dump(status, f, indent=2)
        except Exception as e:
            logger.error(f"Error updating bot status: {e}")

    def update_trades(self, trades: List[Dict[str, Any]]):
        """Update active trades"""
        try:
            data = {
                'last_updated': datetime.now().isoformat(),
                'active_trades': trades
            }
            with open(self.trades_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error updating trades status: {e}")

    def get_bot_status(self) -> Dict[str, Any]:
        """Get current bot status"""
        try:
            if os.path.exists(self.status_file):
                with open(self.status_file, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"Error reading bot status: {e}")
            return {}

    def get_active_trades(self) -> List[Dict[str, Any]]:
        """Get active trades"""
        try:
            if os.path.exists(self.trades_file):
                with open(self.trades_file, 'r') as f:
                    data = json.load(f)
                    return data.get('active_trades', [])
            return []
        except Exception as e:
            logger.error(f"Error reading trades: {e}")
            return []

    def format_status_message(self) -> str:
        """Format status for Telegram"""
        status = self.get_bot_status()
        trades = self.get_active_trades()

        # Basic status
        msg = "🤖 Bot Status Report\n\n"

        # Bot health
        health = status.get('health', {})
        msg += f"Status: {'🟢 Running' if health.get('is_running') else '🔴 Stopped'}\n"
        msg += f"Uptime: {health.get('uptime', 'N/A')}\n"
        msg += f"Last Check: {health.get('last_check', 'N/A')}\n\n"

        # Balance
        balance = status.get('balance', {})
        msg += "💰 Balance:\n"
        for asset, amount in balance.items():
            msg += f"{asset}: {amount:.8f}\n"
        msg += "\n"

        # Active trades
        msg += f"📊 Active Trades ({len(trades)}):\n"
        for trade in trades:
            msg += f"\n{trade['symbol']}:\n"
            msg += f"Entry: {trade['entry_price']:.8f}\n"
            msg += f"Current: {trade.get('current_price', 'N/A')}\n"
            msg += f"P/L: {trade.get('pnl', 0):.2f}%\n"

        # Performance
        perf = status.get('performance', {})
        msg += f"\n📈 Performance (24h):\n"
        msg += f"Trades: {perf.get('total_trades', 0)}\n"
        msg += f"Win Rate: {perf.get('win_rate', 0):.1f}%\n"
        msg += f"Profit: {perf.get('total_profit', 0):.2f}%\n"

        return msg
