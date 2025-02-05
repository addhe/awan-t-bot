from typing import Dict, Any, List, Optional, Tuple
import logging
import time
from dataclasses import dataclass
import numpy as np
from datetime import datetime

@dataclass
class Position:
    id: str
    symbol: str
    side: str
    entry_price: float
    current_price: float
    size: float
    unrealized_pnl: float
    leverage: int
    created_at: datetime
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

class PositionManager:
    def __init__(self, exchange: Any, risk_manager: Any):
        self.exchange = exchange
        self.risk_manager = risk_manager
        self.positions: Dict[str, Position] = {}
        self.order_history: List[Dict[str, Any]] = []

    def open_position(self, side: str, size: float, entry_price: float,
                     stop_loss: float, take_profit: float) -> Optional[Position]:
        try:
            # Validate position parameters
            if not self._validate_position_params(side, size, entry_price):
                return None

            # Check risk limits
            if not self.risk_manager.check_position_risk(size, entry_price):
                logging.warning("Position exceeds risk limits")
                return None

            # Place the order
            order = self.exchange.create_order(
                symbol=self.exchange.symbol,
                type='market',
                side=side,
                amount=size
            )

            if not order:
                return None

            # Create position object
            position = Position(
                id=order['id'],
                symbol=self.exchange.symbol,
                side=side,
                entry_price=entry_price,
                current_price=entry_price,
                size=size,
                unrealized_pnl=0,
                leverage=self.exchange.leverage,
                created_at=datetime.now(),
                stop_loss=stop_loss,
                take_profit=take_profit
            )

            # Set stop loss and take profit
            self._set_stop_loss(position)
            self._set_take_profit(position)

            # Store position
            self.positions[position.id] = position

            return position

        except Exception as e:
            logging.error(f"Error opening position: {e}")
            return None

    def close_position(self, position_id: str, reason: str = "manual") -> bool:
        try:
            position = self.positions.get(position_id)
            if not position:
                return False

            # Close the position
            close_order = self.exchange.create_order(
                symbol=position.symbol,
                type='market',
                side='sell' if position.side == 'buy' else 'buy',
                amount=position.size
            )

            if close_order:
                # Calculate P&L
                exit_price = float(close_order['price'])
                pnl = self._calculate_pnl(position, exit_price)

                # Record trade history
                self.order_history.append({
                    'position_id': position_id,
                    'entry_price': position.entry_price,
                    'exit_price': exit_price,
                    'size': position.size,
                    'side': position.side,
                    'pnl': pnl,
                    'close_reason': reason,
                    'duration': (datetime.now() - position.created_at).total_seconds()
                })

                # Remove position
                del self.positions[position_id]
                return True

            return False

        except Exception as e:
            logging.error(f"Error closing position: {e}")
            return False

    def update_positions(self) -> None:
        """Update all position states with current market data."""
        try:
            for pos_id, position in list(self.positions.items()):
                # Fetch current market price
                ticker = self.exchange.fetch_ticker(position.symbol)
                current_price = ticker['last']

                # Update position state
                position.current_price = current_price
                position.unrealized_pnl = self._calculate_pnl(position, current_price)

                # Check stop loss and take profit
                if self._should_close_position(position):
                    self.close_position(pos_id, "sl_tp_hit")

        except Exception as e:
            logging.error(f"Error updating positions: {e}")

    def _validate_position_params(self, side: str, size: float,
                                entry_price: float) -> bool:
        """Validate position parameters."""
        if side not in ['buy', 'sell']:
            logging.error(f"Invalid side: {side}")
            return False

        if size <= 0:
            logging.error(f"Invalid size: {size}")
            return False

        if entry_price <= 0:
            logging.error(f"Invalid entry price: {entry_price}")
            return False

        return True

    def _calculate_pnl(self, position: Position, current_price: float) -> float:
        """Calculate position P&L."""
        price_diff = current_price - position.entry_price
        if position.side == 'sell':
            price_diff = -price_diff

        return price_diff * position.size

    def _should_close_position(self, position: Position) -> bool:
        """Check if position should be closed based on SL/TP."""
        if position.side == 'buy':
            if (position.stop_loss and position.current_price <= position.stop_loss) or \
               (position.take_profit and position.current_price >= position.take_profit):
                return True
        else:
            if (position.stop_loss and position.current_price >= position.stop_loss) or \
               (position.take_profit and position.current_price <= position.take_profit):
                return True

        return False

    def _set_stop_loss(self, position: Position) -> bool:
        """Set stop loss order for position."""
        try:
            if position.stop_loss:
                self.exchange.create_order(
                    symbol=position.symbol,
                    type='stop',
                    side='sell' if position.side == 'buy' else 'buy',
                    amount=position.size,
                    price=position.stop_loss,
                    params={'stopPrice': position.stop_loss}
                )
                return True
            return False
        except Exception as e:
            logging.error(f"Error setting stop loss: {e}")
            return False

    def _set_take_profit(self, position: Position) -> bool:
        """Set take profit order for position."""
        try:
            if position.take_profit:
                self.exchange.create_order(
                    symbol=position.symbol,
                    type='limit',
                    side='sell' if position.side == 'buy' else 'buy',
                    amount=position.size,
                    price=position.take_profit
                )
                return True
            return False
        except Exception as e:
            logging.error(f"Error setting take profit: {e}")
            return False

    def get_position_metrics(self) -> Dict[str, Any]:
        """Get current position metrics."""
        total_pnl = 0
        total_exposure = 0

        for position in self.positions.values():
            total_pnl += position.unrealized_pnl
            total_exposure += abs(position.size * position.current_price)

        return {
            'total_positions': len(self.positions),
            'total_pnl': total_pnl,
            'total_exposure': total_exposure,
            'positions': [vars(p) for p in self.positions.values()]
        }
