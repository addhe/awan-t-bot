"""
Bot status monitoring and reporting
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

from src.utils.structured_logger import get_logger, log_call
from src.utils.error_handlers import handle_strategy_errors, retry_with_backoff


# Custom exceptions
class StatusMonitorError(Exception):
    """Base exception for status monitor errors"""

    def __init__(
        self,
        message: str,
        original_error: Optional[Exception] = None,
        details: Dict[str, Any] = None,
    ):
        self.message = message
        self.original_error = original_error
        self.details = details or {}
        super().__init__(self.message)

    def __str__(self):
        if self.original_error:
            return (
                f"{self.message} (Original error: {str(self.original_error)})"
            )
        return self.message


class FileOperationError(StatusMonitorError):
    """Raised when file operations (read/write) fail"""

    pass


logger = get_logger(__name__)


class BotStatusMonitor:
    def __init__(self, status_dir: str = "status"):
        self.status_dir = status_dir
        self.status_file = os.path.join(status_dir, "bot_status.json")
        self.trades_file = os.path.join(status_dir, "active_trades.json")
        self.completed_trades_file = os.path.join(
            status_dir, "completed_trades.json"
        )
        self._ensure_status_dir()

    @log_call()
    def _ensure_status_dir(self):
        """Ensure status directory exists"""
        try:
            Path(self.status_dir).mkdir(parents=True, exist_ok=True)
            logger.debug(
                f"Ensured status directory exists: {self.status_dir}"
            )
        except Exception as e:
            logger.error(
                f"Failed to create status directory: {self.status_dir}",
                exc_info=True,
            )
            raise FileOperationError(
                f"Failed to create status directory: {self.status_dir}", e
            )

    @handle_strategy_errors(notify=False)
    @log_call()
    def update_bot_status(self, status: Dict[str, Any]):
        """Update bot status"""
        try:
            status["last_updated"] = datetime.now().isoformat()
            with open(self.status_file, "w") as f:
                json.dump(status, f, indent=2)
            logger.info(
                "Bot status updated successfully"
            )
        except Exception as e:
            error_msg = "Error updating bot status"
            logger.error(
                error_msg, exc_info=True, status_file=self.status_file
            )
            raise FileOperationError(
                error_msg, e, {"status_file": self.status_file}
            )

    @handle_strategy_errors(notify=False)
    @log_call()
    def update_trades(self, trades: List[Dict[str, Any]]):
        """Update active trades"""
        try:
            data = {
                "last_updated": datetime.now().isoformat(),
                "active_trades": trades,
            }
            with open(self.trades_file, "w") as f:
                json.dump(data, f, indent=2)
            logger.info(
                "Active trades updated successfully",
                trade_count=len(trades)
            )
        except Exception as e:
            error_msg = "Error updating trades status"
            logger.error(
                error_msg,
                exc_info=True,
                trades_file=self.trades_file,
                trade_count=len(trades),
            )
            raise FileOperationError(
                error_msg, e, {"trades_file": self.trades_file}
            )

    @retry_with_backoff(max_retries=3)
    @log_call()
    def get_bot_status(self) -> Dict[str, Any]:
        """Get current bot status"""
        try:
            if os.path.exists(self.status_file):
                with open(self.status_file, "r") as f:
                    status = json.load(f)
                    logger.debug(
                        "Retrieved bot status successfully"
                    )
                    return status
            logger.info(
                "No existing status file found, returning empty status"
            )
            return {}
        except json.JSONDecodeError as e:
            error_msg = "Error decoding bot status JSON"
            logger.error(
                error_msg, exc_info=True, status_file=self.status_file
            )
            raise FileOperationError(
                error_msg, e, {"status_file": self.status_file}
            )
        except Exception as e:
            error_msg = "Error reading bot status"
            logger.error(
                error_msg, exc_info=True, status_file=self.status_file
            )
            raise FileOperationError(
                error_msg, e, {"status_file": self.status_file}
            )

    @retry_with_backoff(max_retries=3)
    @log_call()
    def get_active_trades(self) -> List[Dict[str, Any]]:
        """Get active trades"""
        try:
            if os.path.exists(self.trades_file):
                with open(self.trades_file, "r") as f:
                    data = json.load(f)
                    trades = data.get("active_trades", [])
                    logger.debug(
                        "Retrieved active trades successfully",
                        trade_count=len(trades),
                    )
                    return trades
            logger.info("No existing trades file found, returning empty list")
            return []
        except json.JSONDecodeError as e:
            error_msg = "Error decoding active trades JSON"
            logger.error(
                error_msg, exc_info=True, trades_file=self.trades_file
            )
            raise FileOperationError(
                error_msg, e, {"trades_file": self.trades_file}
            )
        except Exception as e:
            error_msg = "Error reading active trades"
            logger.error(
                error_msg, exc_info=True, trades_file=self.trades_file
            )
            raise FileOperationError(
                error_msg, e, {"trades_file": self.trades_file}
            )

    @retry_with_backoff(max_retries=3)
    @log_call()
    def get_completed_trades(self, since=None) -> List[Dict[str, Any]]:
        """Get completed trades since given datetime"""
        try:
            if os.path.exists(self.completed_trades_file):
                with open(self.completed_trades_file, "r") as f:
                    data = json.load(f)
                    trades = data.get("completed_trades", [])
                    if since:
                        trades = [
                            t
                            for t in trades
                            if datetime.fromisoformat(t["close_time"]) >= since
                        ]
                    logger.debug(
                        "Retrieved completed trades successfully",
                        trade_count=len(trades),
                        since=since.isoformat() if since else None,
                    )
                    return trades
            logger.info(
                "No existing completed trades file found, returning empty list"
            )
            return []
        except json.JSONDecodeError as e:
            error_msg = "Error decoding completed trades JSON"
            logger.error(
                error_msg,
                exc_info=True,
                completed_trades_file=self.completed_trades_file,
            )
            raise FileOperationError(
                error_msg,
                e,
                {"completed_trades_file": self.completed_trades_file},
            )
        except Exception as e:
            error_msg = "Error reading completed trades"
            logger.error(
                error_msg,
                exc_info=True,
                completed_trades_file=self.completed_trades_file,
            )
            raise FileOperationError(
                error_msg,
                e,
                {"completed_trades_file": self.completed_trades_file},
            )

    @handle_strategy_errors(notify=True)
    @log_call()
    def save_completed_trade(self, trade: Dict[str, Any]):
        """
        Save a completed trade to history.

        Args:
            trade (Dict[str, Any]): Trade information including symbol,
                entry_price, exit_price, quantity, and profit
        """
        try:
            # Load existing trades
            completed_trades = []
            if os.path.exists(self.completed_trades_file):
                with open(self.completed_trades_file, "r") as f:
                    data = json.load(f)
                    completed_trades = data.get("completed_trades", [])
                    logger.debug(
                        "Loaded existing completed trades",
                        count=len(completed_trades),
                    )

            # Add close time
            trade["close_time"] = datetime.now().isoformat()

            # Append new trade
            completed_trades.append(trade)

            # Save updated trades
            with open(self.completed_trades_file, "w") as f:
                json.dump(
                    {
                        "last_updated": datetime.now().isoformat(),
                        "completed_trades": completed_trades,
                    },
                    f,
                    indent=2,
                )

            logger.info(
                "Completed trade saved successfully",
                symbol=trade.get("symbol"),
                profit=trade.get("profit"),
                reason=trade.get("close_reason"),
            )

        except json.JSONDecodeError as e:
            error_msg = "Error decoding existing completed trades JSON"
            logger.error(
                error_msg,
                exc_info=True,
                completed_trades_file=self.completed_trades_file,
                symbol=trade.get("symbol"),
            )
            raise FileOperationError(
                error_msg,
                e,
                {
                    "completed_trades_file": self.completed_trades_file,
                    "symbol": trade.get("symbol"),
                },
            )
        except Exception as e:
            error_msg = "Error saving completed trade"
            logger.error(
                error_msg,
                exc_info=True,
                completed_trades_file=self.completed_trades_file,
                symbol=trade.get("symbol"),
            )
            raise FileOperationError(
                error_msg,
                e,
                {
                    "completed_trades_file": self.completed_trades_file,
                    "symbol": trade.get("symbol"),
                },
            )

    @handle_strategy_errors(notify=False)
    @log_call()
    def format_status_message(self) -> str:
        """Format status for Telegram"""
        try:
            status = self.get_bot_status()
            trades = self.get_active_trades()
            logger.debug(
                "Retrieved data for status message",
                status_size=len(status),
                trade_count=len(trades),
            )

            # Basic status
            msg = "🤖 Bot Status Report\n\n"

            # Bot health
            health = status.get("health", {})
            msg += (
                (
                    (
                        f"Status: {'🟢 Running' if health.get('is_running') else '🔴 Stopped'}\n"  # noqa: E501
                    )  # noqa: E501
                )
            )
            msg += f"Uptime: {health.get('uptime', 'N/A')}\n"
            msg += f"Last Check: {health.get('last_check', 'N/A')}\n\n"

            # Balance
            balance = status.get("balance", {})
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
            perf = status.get("performance", {})
            msg += "\n📈 Performance (24h):\n"
            msg += f"Trades: {perf.get('total_trades', 0)}\n"
            msg += f"Win Rate: {perf.get('win_rate', 0):.1f}%\n"
            msg += f"Profit: {perf.get('total_profit', 0):.2f}%\n"

            logger.debug(
                "Status message formatted successfully",
                msg_length=len(msg)
            )
            return msg

        except Exception as e:  # noqa: F841 (variable not used)
            # e is intentionally unused for logging only
            pass  # noqa: F841
            logger.error(
                "Error formatting status message",
                exc_info=True
            )
            # Return a minimal error message to avoid breaking the bot
            return "⚠️ Error generating status report. Check logs for details."
