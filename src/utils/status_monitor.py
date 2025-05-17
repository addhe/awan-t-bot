"""
Bot status monitoring and reporting
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
import tempfile

from src.utils.structured_logger import get_logger, log_call
from src.utils.error_handlers import retry_with_backoff


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
        self.status_dir_path = Path(self.status_dir)
        self.status_file = self.status_dir_path / "bot_status.json"
        self.trades_file = self.status_dir_path / "active_trades.json"
        self.completed_trades_file = self.status_dir_path / "completed_trades.json"
        self._ensure_status_dir()

    @log_call()
    def _ensure_status_dir(self):
        """Ensure status directory exists"""
        try:
            self.status_dir_path.mkdir(parents=True, exist_ok=True)
            logger.debug(
                f"Ensured status directory exists: {self.status_dir_path}"
            )
        except Exception as e:
            logger.error(
                f"Failed to create status directory: {self.status_dir_path}",
                exc_info=True,
            )
            raise FileOperationError(
                f"Failed to create status directory: {self.status_dir_path}", e
            )

    def _atomic_write_json(self, target_path: Path, data: Any):
        """Atomically write JSON data to a file."""
        temp_file_path = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False,
                                            dir=target_path.parent,
                                            prefix=target_path.name + '.',
                                            suffix='.tmp') as tmp_f:
                temp_file_path = Path(tmp_f.name)
                json.dump(data, tmp_f, indent=2)

            os.replace(temp_file_path, target_path)
            logger.debug(f"Atomically wrote JSON to {target_path}")
        except Exception as e:
            error_msg = f"Error during atomic write to {target_path}"
            logger.error(error_msg, exc_info=True)
            if temp_file_path and temp_file_path.exists():
                try:
                    temp_file_path.unlink()
                except Exception as cleanup_e:
                    logger.error(f"Failed to cleanup temp file {temp_file_path}: {cleanup_e}")
            raise FileOperationError(error_msg, e, {"target_file": str(target_path)})

    @log_call()
    def update_bot_status(self, status: Dict[str, Any]):
        """Update bot status atomically."""
        status["last_updated"] = datetime.now().isoformat()
        try:
            self._atomic_write_json(self.status_file, status)
            logger.info("Bot status updated successfully")
        except FileOperationError:
            raise
        except Exception as e:
            error_msg = "Unexpected error updating bot status"
            logger.error(error_msg, exc_info=True)
            raise FileOperationError(error_msg, e, {"status_file": str(self.status_file)})

    @log_call()
    def update_confidence_levels(self, confidence_data: Dict[str, Any]):
        """Update confidence levels for trading pairs.

        Args:
            confidence_data: Dictionary with symbol as key and confidence info as value
                Example: {"BTCUSDT": {"confidence": 0.65, "timestamp": "2025-05-10T12:00:00"}}
        """
        confidence_file = self.status_dir_path / "confidence_levels.json"

        try:
            # Load existing data if available
            existing_data = {}
            if confidence_file.exists():
                try:
                    with open(confidence_file, "r") as f:
                        existing_data = json.load(f)
                except json.JSONDecodeError:
                    logger.warning("Could not decode existing confidence file, creating new one")

            # Update with new data
            data_to_save = existing_data.copy()
            data_to_save.update(confidence_data)
            data_to_save["last_updated"] = datetime.now().isoformat()

            # Write to file
            self._atomic_write_json(confidence_file, data_to_save)
            logger.info("Confidence levels updated successfully")
        except Exception as e:
            error_msg = "Error updating confidence levels"
            logger.error(error_msg, exc_info=True)
            raise FileOperationError(error_msg, e, {"confidence_file": str(confidence_file)})

    @log_call()
    def get_confidence_levels(self) -> Dict[str, Any]:
        """Get current confidence levels for all trading pairs.

        Returns:
            Dictionary with confidence levels and timestamps
        """
        confidence_file = self.status_dir_path / "confidence_levels.json"

        try:
            if not confidence_file.exists():
                logger.debug("No confidence levels file found")
                return {}

            with open(confidence_file, "r") as f:
                data = json.load(f)
                logger.debug("Loaded confidence levels successfully")
                return data
        except Exception as e:
            error_msg = "Error reading confidence levels"
            logger.error(error_msg, exc_info=True)
            return []

    @retry_with_backoff(max_retries=3)
    @log_call()
    def get_closed_trades(self, since=None) -> List[Dict[str, Any]]:
        """Get closed trades (alias for get_completed_trades)

        This method is an alias for get_completed_trades to maintain
        compatibility with DataSyncManager

        Args:
            since: Optional datetime to filter trades

        Returns:
            List of closed trades
        """
        return self.get_completed_trades(since)

    @log_call()
    def update_trades(self, trades: List[Dict[str, Any]]):
        """Update active trades atomically."""
        data = {
            "last_updated": datetime.now().isoformat(),
            "active_trades": trades,
        }
        try:
            self._atomic_write_json(self.trades_file, data)
            logger.info(
                "Active trades updated successfully",
                trade_count=len(trades)
            )
        except FileOperationError:
            raise
        except Exception as e:
            error_msg = "Unexpected error updating active trades"
            logger.error(error_msg, exc_info=True)
            raise FileOperationError(error_msg, e, {"trades_file": str(self.trades_file)})

    @log_call()
    def update_active_trades(self, active_trades: Dict[str, Any]):
        """Update active trades from position manager.

        Args:
            active_trades: Dictionary with symbol as key and trade info as value
        """
        try:
            # Convert dictionary to list format expected by update_trades
            trades_list = []
            for symbol, trade_data in active_trades.items():
                trade_info = trade_data.copy()  # Make a copy to avoid modifying original
                trade_info["symbol"] = symbol  # Add symbol to the trade info

                # Ensure current_price and pnl are properly set
                if "current_price" not in trade_info and "entry_price" in trade_info:
                    logger.warning(f"Missing current_price for {symbol}, using entry_price")
                    trade_info["current_price"] = trade_info["entry_price"]

                # Calculate pnl if not present but we have prices
                if "pnl" not in trade_info and "current_price" in trade_info and "entry_price" in trade_info:
                    try:
                        entry = float(trade_info["entry_price"])
                        current = float(trade_info["current_price"])
                        trade_info["pnl"] = round(((current - entry) / entry) * 100, 2)
                        logger.debug(f"Calculated pnl for {symbol}: {trade_info['pnl']}%")
                    except (ValueError, TypeError) as e:
                        logger.error(f"Error calculating pnl for {symbol}: {e}")

                trades_list.append(trade_info)

            # Call existing update_trades method
            self.update_trades(trades_list)
            logger.info(f"Updated {len(trades_list)} active trades via update_active_trades")
        except Exception as e:
            error_msg = "Error in update_active_trades"
            logger.error(error_msg, exc_info=True)
            # Continue without raising to avoid breaking the main loop

    @log_call()
    def update_status_metrics(self, metrics: Dict[str, Any]):
        """Update bot status metrics.

        Args:
            metrics: Dictionary with status metrics like uptime, active_trades, etc.
        """
        try:
            # Get current status or initialize new one
            current_status = self.get_bot_status() or {}

            # Update metrics in status
            if "metrics" not in current_status:
                current_status["metrics"] = {}

            # Update with new metrics
            current_status["metrics"].update(metrics)

            # Update last_updated timestamp
            current_status["last_updated"] = datetime.now().isoformat()

            # Save updated status
            self.update_bot_status(current_status)

            logger.info("Updated bot status metrics", metrics_count=len(metrics))
        except Exception as e:
            error_msg = "Error in update_status_metrics"
            logger.error(error_msg, exc_info=True)
            # Continue without raising to avoid breaking the main loop

    @retry_with_backoff(max_retries=3)
    @log_call()
    def get_bot_status(self) -> Dict[str, Any]:
        """Get current bot status"""
        try:
            if self.status_file.exists():
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
            if self.trades_file.exists():
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
            if self.completed_trades_file.exists():
                with open(self.completed_trades_file, "r") as f:
                    data = json.load(f)
                    all_trades = data.get("completed_trades", [])
                    filtered_trades = []
                    if since:
                        # Convert since to datetime if it's a string
                        if isinstance(since, str):
                            try:
                                since = datetime.fromisoformat(since)
                            except ValueError:
                                logger.warning(
                                    f"Invalid date format for 'since': {since}, using all trades"
                                )
                                return all_trades

                        # Filter trades by date
                        for trade in all_trades:
                            trade_time = trade.get("exit_time") or trade.get("entry_time")
                            if not trade_time:
                                continue

                            try:
                                if isinstance(trade_time, str):
                                    trade_dt = datetime.fromisoformat(trade_time)
                                else:
                                    trade_dt = trade_time

                                if trade_dt >= since:
                                    filtered_trades.append(trade)
                            except ValueError:
                                # If date parsing fails, include the trade anyway
                                filtered_trades.append(trade)

                        logger.info(
                            f"Filtered {len(filtered_trades)} trades since {since}",
                            original_count=len(all_trades),
                            filtered_count=len(filtered_trades),
                        )
                        return filtered_trades
                    else:
                        # Return all trades if no since filter
                        logger.info(f"Retrieved {len(all_trades)} completed trades")
                        return all_trades
            else:
                logger.info(
                    "No completed trades file found",
                    file=str(self.completed_trades_file),
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
            error_msg = "Error retrieving completed trades"
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

    @retry_with_backoff(max_retries=3)
    @log_call()
    def get_closed_trades(self, since=None) -> List[Dict[str, Any]]:
        """Get closed trades (alias for get_completed_trades)

        This method is an alias for get_completed_trades to maintain
        compatibility with DataSyncManager

        Args:
            since: Optional datetime to filter trades

        Returns:
            List of closed trades
        """
        return self.get_completed_trades(since)

    @log_call()
    def save_completed_trade(self, trade: Dict[str, Any]):
        """
        Save a completed trade to history atomically.

        Args:
            trade (Dict[str, Any]): Trade information including symbol,
                entry_price, exit_price, quantity, and profit
        """
        try:
            completed_trades = []
            if self.completed_trades_file.exists():
                try:
                    with open(self.completed_trades_file, "r") as f:
                        data = json.load(f)
                        completed_trades = data.get("completed_trades", [])
                        logger.debug(
                            "Loaded existing completed trades",
                            count=len(completed_trades),
                        )
                except json.JSONDecodeError as e:
                    error_msg = "Error decoding existing completed trades JSON, will overwrite if possible."
                    logger.error(error_msg, exc_info=True, completed_trades_file=self.completed_trades_file)
                    completed_trades = []

            trade["close_time"] = datetime.now().isoformat()

            completed_trades.append(trade)

            data_to_save = {
                "last_updated": datetime.now().isoformat(),
                "completed_trades": completed_trades,
            }

            self._atomic_write_json(self.completed_trades_file, data_to_save)

            logger.info(
                "Completed trade saved successfully",
                symbol=trade.get("symbol"),
                profit=trade.get("profit"),
                reason=trade.get("close_reason"),
            )

        except FileOperationError:
            raise
        except Exception as e:
            error_msg = "Unexpected error saving completed trade"
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
                    "completed_trades_file": str(self.completed_trades_file),
                    "symbol": trade.get("symbol"),
                },
            )

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

            msg = "🤖 Bot Status Report\n\n"

            health = status.get("health", {})
            status_line = f"Status: {'🟢 Running' if health.get('is_running') else '🔴 Stopped'}"
            msg += f"{status_line}\n"
            msg += f"Uptime: {health.get('uptime', 'N/A')}\n"
            msg += f"Last Check: {health.get('last_check', 'N/A')}\n\n"

            balance = status.get("balance", {})
            msg += "💰 Balance:\n"
            # Filter out assets with LD prefix (locked/staked assets)
            tradable_assets = {asset: amount for asset, amount in balance.items() if not asset.startswith('LD')}

            # Display tradable assets first
            for asset, amount in sorted(tradable_assets.items()):
                msg += f"{asset}: {amount:.8f}\n"

            # Optionally add a separator and summary for LD assets if needed
            ld_assets = {asset: amount for asset, amount in balance.items() if asset.startswith('LD')}
            if ld_assets and False:  # Set to True if you want to show LD assets in a separate section
                msg += "\n🔒 Locked/Staked Assets:\n"
                for asset, amount in sorted(ld_assets.items()):
                    msg += f"{asset}: {amount:.8f}\n"
            msg += "\n"

            msg += f"📊 Active Trades ({len(trades)}):\n"
            for trade in trades:
                msg += f"\n{trade['symbol']}:\n"
                msg += f"Entry: {trade['entry_price']:.8f}\n"
                # Format current price consistently with entry price
                current_price = trade.get('current_price', 'N/A')
                if isinstance(current_price, (int, float)):
                    msg += f"Current: {current_price:.8f}\n"
                elif isinstance(current_price, str) and current_price.replace('.', '', 1).isdigit():
                    # Handle string representation of numbers
                    msg += f"Current: {float(current_price):.8f}\n"
                else:
                    msg += f"Current: {current_price}\n"

                # Format P/L with proper handling of different data types
                pnl = trade.get('pnl', 0)
                # Check if we have a pre-formatted P/L string
                pnl_formatted = trade.get('pnl_formatted')
                
                if pnl_formatted and isinstance(pnl_formatted, str):
                    # Use the pre-formatted string if available
                    msg += f"P/L: {pnl_formatted}\n"
                elif isinstance(pnl, (int, float)):
                    # Format as percentage with 2 decimal places
                    msg += f"P/L: {pnl:.2f}%\n"
                elif isinstance(pnl, str) and pnl.replace('-', '', 1).replace('.', '', 1).isdigit():
                    # Handle string representation of numbers including negative values
                    msg += f"P/L: {float(pnl):.2f}%\n"
                else:
                    # Fallback to 0.00% if P/L is not in expected format
                    msg += "P/L: 0.00%\n"

                # Add confidence if available
                if 'confidence' in trade:
                    msg += f"Confidence: {trade.get('confidence', 0):.2f}\n"

            perf = status.get("performance", {})
            msg += "\n📈 Performance (24h):\n"
            msg += f"Trades: {perf.get('total_trades', 0)}\n"
            msg += f"Win Rate: {perf.get('win_rate', 0):.1f}%\n"
            msg += f"Profit: {perf.get('total_profit', 0):.2f}%\n"

            # Add current confidence levels if available
            try:
                confidence_data = self.get_confidence_levels()
                if confidence_data and any(k != "last_updated" for k in confidence_data.keys()):
                    msg += "\n🎯 Current Confidence Levels:\n"
                    for symbol, data in confidence_data.items():
                        if symbol != "last_updated" and isinstance(data, dict) and "confidence" in data:
                            # Format timestamp
                            timestamp_str = ""
                            try:
                                # Check for updated_at (new format) or timestamp (old format)
                                if "updated_at" in data:
                                    timestamp_str = f" (updated: {data['updated_at']})"
                                elif "timestamp" in data:
                                    dt = datetime.fromisoformat(data["timestamp"])
                                    timestamp_str = f" (updated: {dt.strftime('%H:%M:%S')})"
                            except Exception as ts_error:
                                logger.error(f"Error formatting timestamp: {ts_error}")
                                pass

                            msg += f"{symbol}: {data['confidence']:.2f}{timestamp_str}\n"
            except Exception as e:
                logger.error(f"Error adding confidence levels to status: {str(e)}")
                # Continue without confidence levels

            logger.debug(
                "Status message formatted successfully",
                msg_length=len(msg)
            )
            return msg

        except Exception as e:
            logger.error(
                "Error formatting status message",
                exc_info=True
            )
            return "⚠️ Error generating status report. Check logs for details."
