import os
import logging
import requests
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class TelegramConfig:
    bot_token: str
    chat_id: str

    @classmethod
    def from_env(cls) -> 'TelegramConfig':
        return cls(
            bot_token=os.environ.get('TELEGRAM_BOT_TOKEN', ''),
            chat_id=os.environ.get('TELEGRAM_CHAT_ID', '')
        )

def send_telegram_notification(message: str) -> bool:
    """Send notification via Telegram."""
    try:
        config = TelegramConfig.from_env()
        if not config.bot_token or not config.chat_id:
            logging.error("Telegram configuration missing")
            return False

        url = f"https://api.telegram.org/bot{config.bot_token}/sendMessage"
        payload = {
            "chat_id": config.chat_id,
            "text": message,
            "parse_mode": "HTML"
        }

        response = requests.post(url, json=payload)
        if response.status_code == 200:
            logging.info(f"Telegram notification sent: {message}")
            return True
        else:
            logging.error(f"Failed to send Telegram notification: {response.text}")
            return False

    except Exception as e:
        logging.error(f"Error sending Telegram notification: {e}")
        return False

class SystemMonitor:
    def __init__(self, exchange: Any, config: Dict[str, Any]):
        self.exchange = exchange
        self.config = config
        self.telegram_config = TelegramConfig.from_env()
        self.last_health_check = datetime.now()
        self.health_check_interval = 300  # 5 minutes

    def check_exchange_health(self) -> bool:
        """Check if exchange is healthy and responding."""
        try:
            self.exchange.load_markets()
            self.last_health_check = datetime.now()
            logging.info("Exchange health check: OK")
            return True
        except Exception as e:
            logging.critical(f"Exchange health check failed: {e}")
            self.send_notification(f"🚨 CRITICAL: Exchange health check failed: {e}")
            return False

    def send_notification(self, message: str) -> bool:
        """Send notification using Telegram."""
        return send_telegram_notification(message)

    def fetch_position_details(self) -> Dict[str, Any]:
        """Fetch current position details."""
        try:
            positions = self.exchange.fetch_positions([self.config['symbol']])
            position_details = {
                'buy': 0,
                'sell': 0,
                'total_buy': 0.0,
                'total_sell': 0.0,
                'unrealized_pnl': 0.0
            }

            for position in positions:
                position_size = float(position['contracts'])
                if position_size > 0:
                    position_details['buy'] += 1
                    position_details['total_buy'] += position_size
                    position_details['unrealized_pnl'] += float(position.get('unrealizedPnl', 0))
                elif position_size < 0:
                    position_details['sell'] += 1
                    position_details['total_sell'] += abs(position_size)
                    position_details['unrealized_pnl'] += float(position.get('unrealizedPnl', 0))

            return position_details
        except Exception as e:
            logging.error(f"Error fetching position details: {e}")
            return {
                'buy': 0,
                'sell': 0,
                'total_buy': 0.0,
                'total_sell': 0.0,
                'unrealized_pnl': 0.0
            }

    def cleanup_old_orders(self) -> None:
        """Cancel old pending orders."""
        try:
            open_orders = self.exchange.fetch_open_orders(symbol=self.config['symbol'])
            current_time = self.exchange.milliseconds()

            for order in open_orders:
                order_age = current_time - order['timestamp']
                # Cancel orders older than 1 hour
                if order_age > 3600000:  # 1 hour in milliseconds
                    self.exchange.cancel_order(order['id'])
                    logging.info(f"Cancelled old order {order['id']}")
        except Exception as e:
            logging.error(f"Error cleaning up old orders: {e}")

    def emergency_stop(self, reason: str) -> bool:
        """Emergency stop: close all positions and cancel all orders."""
        try:
            # Cancel all open orders
            self.exchange.cancel_all_orders(symbol=self.config['symbol'])

            # Close all positions
            positions = self.fetch_position_details()
            if positions['total_buy'] > 0 or positions['total_sell'] > 0:
                self.exchange.close_positions([self.config['symbol']])

            self.send_notification(f"🚨 EMERGENCY STOP EXECUTED\nReason: {reason}")
            return True
        except Exception as e:
            logging.critical(f"Emergency stop failed: {e}")
            self.send_notification(f"🚨 EMERGENCY STOP FAILED: {e}")
            return False

    def monitor_system_health(self) -> bool:
        """Periodic system health check."""
        try:
            current_time = datetime.now()
            if (current_time - self.last_health_check).total_seconds() >= self.health_check_interval:
                # Check exchange connectivity
                if not self.check_exchange_health():
                    return False

                # Check balance
                balance = self.exchange.fetch_balance()
                usdt_balance = balance['USDT']['free']
                if usdt_balance < self.config['min_balance']:
                    self.send_notification(f"⚠️ Low balance warning: {usdt_balance:.2f} USDT")

                # Check position health
                position_details = self.fetch_position_details()
                if abs(position_details['unrealized_pnl']) > usdt_balance * 0.2:  # 20% of balance
                    self.send_notification("⚠️ Large unrealized PnL detected")

                # Cleanup old orders
                self.cleanup_old_orders()

                self.last_health_check = current_time

            return True

        except Exception as e:
            logging.error(f"System health monitoring failed: {e}")
            return False
