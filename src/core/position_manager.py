"""
Position and trade management
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional

from src.utils.status_monitor import BotStatusMonitor
from src.exchange.connector import ExchangeConnector
from src.utils.error_handlers import (
    handle_exchange_errors,
    handle_strategy_errors,
)
from src.utils.structured_logger import get_logger

logger = get_logger(__name__)


class PositionManager:
    """Manages trading positions, entry/exit, and trade tracking"""

    def __init__(
        self,
        exchange: ExchangeConnector,
        trading_config: Dict[str, Any],
        monitor: BotStatusMonitor,
    ):
        """Initialize position manager

        Args:
            exchange: Exchange connector
            trading_config: Trading configuration
            monitor: Status monitor for recording trades
        """
        self.exchange = exchange
        self.config = trading_config
        self.monitor = monitor
        self.active_trades = {}

        # Load active trades from status file
        self._load_active_trades_from_status()

    async def _check_and_apply_dca(self, symbol: str, current_price: float) -> bool:
        """
        Check if DCA should be applied and execute if conditions are met
        
        Args:
            symbol: Trading pair symbol
            current_price: Current market price
            
        Returns:
            bool: True if DCA was applied, False otherwise
        """
        try:
            if not self.config.get('dca', {}).get('enabled', False):
                return False
                
            if symbol not in self.active_trades:
                return False
                
            trade = self.active_trades[symbol]
            entry_price = trade.get('entry_price', 0)
            
            if entry_price <= 0:
                return False
                
            # Calculate price drop percentage
            price_drop = (entry_price - current_price) / entry_price
            dca_config = self.config.get('dca', {})
            
            # Check if price has dropped enough to trigger DCA
            if price_drop < dca_config.get('price_drop_percentage', 0.03):
                return False
                
            # Check max DCA levels
            dca_level = trade.get('dca_level', 0)
            if dca_level >= dca_config.get('max_dca_levels', 3):
                logger.info(f"Max DCA levels reached for {symbol}")
                return False
                
            # Check available balance
            balance = await self.exchange.get_balance('USDT')
            min_balance_required = dca_config.get('min_balance_required', 0.1) * self.config.get('position_size', 0.02)
            if balance < min_balance_required:
                logger.warning(f"Insufficient balance for DCA on {symbol}. Required: {min_balance_required}, Available: {balance}")
                return False
                
            # Calculate DCA position size (increases with each DCA level)
            base_position_size = self.config.get('position_size', 0.02) * (dca_config.get('dca_multiplier', 1.5) ** dca_level)
            
            # Execute DCA order
            try:
                order = await self.exchange.create_market_buy_order(
                    symbol=symbol,
                    amount=base_position_size,
                    params={'reduceOnly': False}
                )
                
                if order and order.get('status') == 'filled':
                    filled_qty = float(order.get('filled', 0))
                    if filled_qty <= 0:
                        logger.warning(f"DCA order filled with zero quantity for {symbol}")
                        return False
                        
                    # Update trade with new DCA level and average price
                    current_qty = trade.get('quantity', 0)
                    new_quantity = current_qty + filled_qty
                    
                    if new_quantity <= 0:
                        return False
                        
                    new_avg_price = (
                        (trade.get('entry_price', 0) * current_qty) + 
                        (current_price * filled_qty)
                    ) / new_quantity
                    
                    trade.update({
                        'entry_price': new_avg_price,
                        'quantity': new_quantity,
                        'dca_level': dca_level + 1,
                        'last_dca_time': datetime.now().isoformat()
                    })
                    
                    logger.info(
                        f"DCA Level {dca_level + 1} executed for {symbol}",
                        symbol=symbol,
                        dca_level=dca_level + 1,
                        price=current_price,
                        quantity=filled_qty,
                        new_avg_price=new_avg_price,
                        new_quantity=new_quantity
                    )
                    return True
                    
            except Exception as e:
                logger.error(f"Error executing DCA order for {symbol}: {str(e)}", exc_info=True)
                
        except Exception as e:
            logger.error(f"Error in _check_and_apply_dca for {symbol}: {str(e)}", exc_info=True)
            
        return False
        
    def _load_active_trades_from_status(self):
        """Load active trades from status file to ensure consistency"""
        try:
            # Get active trades from status monitor
            status_trades = self.monitor.get_active_trades()

            if status_trades:
                logger.info(f"Loading {len(status_trades)} active trades from status file")

                # Convert to the format expected by position manager
                for trade in status_trades:
                    symbol = trade.get("symbol")
                    if not symbol:
                        continue

                    self.active_trades[symbol] = {
                        "entry_price": trade.get("entry_price", 0),
                        "quantity": trade.get("quantity", 0),
                        "entry_time": trade.get("entry_time", datetime.now().isoformat()),
                        "stop_loss": trade.get("stop_loss", 0),
                        "take_profit": trade.get("take_profit", 0),
                        "confidence": trade.get("confidence", 0.5),
                        "order_id": trade.get("order_id", "")
                    }

                logger.info(f"Loaded {len(self.active_trades)} active trades: {list(self.active_trades.keys())}")
        except Exception as e:
            logger.error(f"Error loading active trades from status: {e}", exc_info=True)

    @handle_exchange_errors(notify=True)
    async def open_position(
        self,
        symbol: str,
        quantity: float,
        risk_level: Dict[str, float],
        confidence: float,
        pair_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Open a new position using a market buy order.

        Uses the actual execution price and quantity from the exchange.

        Args:
            symbol: Trading pair symbol
            quantity: Requested position size (may differ from filled quantity)
            risk_level: Stop loss and take profit levels (based on intended entry initially)
            confidence: Trade confidence (0-1)
            pair_config: Trading pair configuration (unused for now)

        Returns:
            Dict with actual position details if successful, else empty dict:
            {'symbol', 'entry_price', 'quantity', 'stop_loss', 'take_profit', 'order_id'}
        """
        logger.info(
            f"Attempting to open position for {symbol}",
            symbol=symbol,
            requested_quantity=quantity,
            stop_loss_level=risk_level.get("stop_loss"),
            take_profit_level=risk_level.get("take_profit"),
            confidence=confidence,
        )

        # Place market buy order - gets actual execution details
        order_result = await self.exchange.place_market_buy(symbol, quantity)

        # Validate execution details
        actual_entry_price = order_result.get("average_price")
        actual_quantity = order_result.get("filled_quantity")
        order_id = order_result.get("order_id")

        if actual_entry_price is None or actual_quantity is None or actual_quantity <= 0:
            logger.error(
                f"Failed to open position for {symbol}: Invalid execution details.",
                symbol=symbol,
                requested_quantity=quantity,
                order_result=order_result,
            )
            # Optionally, try to cancel the order if ID exists? Depends on desired logic.
            # if order_id:
            #    await self.exchange.cancel_order(order_id, symbol)
            return {}  # Indicate failure

        # Recalculate SL/TP based on actual entry if necessary?
        # For now, assume risk_level was pre-calculated and remains valid
        # Or adjust: risk_level["stop_loss"] = actual_entry_price * (1 - sl_pct)
        stop_loss_price = risk_level.get("stop_loss", 0)
        take_profit_price = risk_level.get("take_profit", 0)

        # Record trade with actual execution details
        self.active_trades[symbol] = {
            "entry_price": actual_entry_price,
            "quantity": actual_quantity,
            "entry_time": datetime.now().isoformat(),
            "stop_loss": stop_loss_price,
            "take_profit": take_profit_price,
            "confidence": confidence,
            "order_id": order_id,  # Store order ID for reference
        }

        # Update active trades in monitor
        await self._update_trades_status()  # Uses the new accurate data

        logger.info(
            f"Position successfully opened for {symbol}",
            symbol=symbol,
            order_id=order_id,
            entry_price=actual_entry_price,
            filled_quantity=actual_quantity,
            stop_loss=stop_loss_price,
            take_profit=take_profit_price,
            position_count=len(self.active_trades),
        )

        # Return actual details
        return {
            "symbol": symbol,
            "entry_price": actual_entry_price,
            "quantity": actual_quantity,
            "stop_loss": stop_loss_price,
            "take_profit": take_profit_price,
            "order_id": order_id,
        }

    @handle_exchange_errors(notify=True)
    async def close_position(
        self, symbol: str, close_reason: str
    ) -> Dict[str, Any]:
        """
        Close an existing position using a market sell order.

        Calculates PnL based on actual entry and exit prices.

        Args:
            symbol: Trading pair symbol
            close_reason: Reason for closing (take_profit, stop_loss, signal, manual)

        Returns:
            Dict with closed position details if successful, else empty dict:
            {'symbol', 'entry_price', 'exit_price', 'quantity', 'profit', 'close_reason', 'order_id'}
        """
        if symbol not in self.active_trades:
            logger.warning(
                f"Attempted to close position for {symbol}, but not found in active trades.",
                symbol=symbol,
                active_trades=list(self.active_trades.keys()),
            )
            return {}  # Indicate failure or already closed

        trade = self.active_trades[symbol]
        entry_price = trade["entry_price"]  # Actual entry price
        quantity = trade["quantity"]  # Actual filled quantity

        # Extract base currency from symbol
        base_currency = None
        if symbol.endswith('USDT'):
            base_currency = symbol[:-4]  # Remove 'USDT'
        elif '/' in symbol:
            base_currency = symbol.split('/')[0]  # Split at '/' and take first part

        # Check if we have enough balance before attempting to sell
        if base_currency:
            # Use the dedicated method to get available balance for this specific asset
            try:
                available_balance = await self.exchange.get_available_balance(base_currency)
            except Exception as e:
                logger.error(f"Error getting available balance for {base_currency}: {str(e)}")
                available_balance = 0

            # Get current price to estimate value
            current_price = 0
            try:
                current_price = await self.exchange.get_current_price(symbol)
            except Exception as e:
                logger.warning(f"Could not get current price for {symbol}: {str(e)}")

            # More strict check with detailed logging and increased safety margin
            required_quantity = quantity * 1.05  # Add 5% margin for fees and price fluctuations
            if available_balance < required_quantity:
                # Check if we have at least 90% of the actual quantity (without safety margin)
                if available_balance >= quantity * 0.9:
                    # We have enough to close most of the position, so use what we have
                    adjusted_quantity = available_balance * 0.99  # Use 99% of available balance to be safe
                    logger.warning(
                        f"⚠️ Insufficient balance to close full position for {symbol}, using available balance",
                        symbol=symbol,
                        required_quantity=required_quantity,
                        actual_quantity=quantity,
                        available_balance=available_balance,
                        adjusted_quantity=adjusted_quantity,
                        base_currency=base_currency,
                        current_price=current_price
                    )

                    # Send notification about partial close
                    from src.utils.telegram_utils import send_telegram_message
                    await send_telegram_message(
                        f"⚠️ Partial close for {symbol} position due to insufficient balance.\n"
                        f"Required: {quantity} {base_currency}\n"
                        f"Available: {available_balance} {base_currency}\n"
                        f"Using: {adjusted_quantity} {base_currency} (99% of available)\n"
                        f"Current price: {current_price}\n"
                        f"This will close approximately {(adjusted_quantity/quantity)*100:.1f}% of your position."
                    )

                    # Update quantity to use available balance
                    quantity = adjusted_quantity

                    # Continue with the trade using adjusted quantity
                else:
                    # Not enough balance to make a meaningful close
                    logger.error(
                        f"❌ Insufficient balance to close position for {symbol}",
                        symbol=symbol,
                        required_quantity=required_quantity,
                        actual_quantity=quantity,
                        available_balance=available_balance,
                        base_currency=base_currency,
                        current_price=current_price,
                        estimated_value=available_balance * current_price if current_price > 0 else 0,
                        margin_factor=1.05  # Document the margin factor we're using
                    )

                    # Send notification about the issue
                    from src.utils.telegram_utils import send_telegram_message
                    await send_telegram_message(
                        f"🔴 Cannot close {symbol} position due to insufficient balance.\n"
                        f"Required: {required_quantity} {base_currency} (includes 5% safety margin)\n"
                        f"Actual position: {quantity} {base_currency}\n"
                        f"Available: {available_balance} {base_currency}\n"
                        f"Current price: {current_price}\n"
                        f"Attempt #{self.active_trades[symbol].get('close_attempts', 0) + 1}\n"
                        f"Please close position manually or add funds to your {base_currency} balance."
                    )

                    # Keep the position in active_trades but mark it as problematic
                    # This allows the system to retry later if balance becomes available
                    self.active_trades[symbol]["close_error"] = "insufficient_balance"
                    self.active_trades[symbol]["close_attempts"] = self.active_trades[symbol].get("close_attempts", 0) + 1
                    self.active_trades[symbol]["pending_close"] = True  # Add flag to prevent opening new positions

                    # PENTING: Jangan hapus dari active_trades meskipun banyak upaya gagal
                    # Ini mencegah bot membuka posisi baru saat posisi lama belum ditutup
                    # if self.active_trades[symbol].get("close_attempts", 0) > 5:
                    #     logger.warning(f"Too many failed attempts to close {symbol}, removing from active trades")
                    #     del self.active_trades[symbol]

                    await self._update_trades_status()

                    # Return a special result indicating position was not closed due to insufficient balance
                    return {
                        "symbol": symbol,
                        "entry_price": entry_price,
                        "exit_price": 0,  # No actual exit since we couldn't sell
                        "quantity": 0,    # No quantity sold
                        "profit": 0,      # Can't calculate profit
                        "close_reason": "insufficient_balance",
                        "order_id": None,
                        "retry": True     # Indicate that we should retry later
                    }

        logger.info(
            f"Attempting to close position for {symbol}",
            symbol=symbol,
            quantity=quantity,
            entry_price=entry_price,
            close_reason=close_reason,
        )

        # Double-check balance right before placing order
        if base_currency:
            try:
                final_check_balance = await self.exchange.get_available_balance(base_currency)
                if final_check_balance < quantity:
                    logger.error(
                        f"Final balance check failed before placing sell order for {symbol}",
                        symbol=symbol,
                        required_quantity=quantity,
                        available_balance=final_check_balance,
                        base_currency=base_currency
                    )
                    # Add to error count but continue with the attempt
                    self.active_trades[symbol]["close_attempts"] = self.active_trades[symbol].get("close_attempts", 0) + 1
            except Exception as e:
                logger.warning(f"Error in final balance check for {symbol}: {str(e)}")

        # Place market sell order - gets actual execution details
        try:
            order_result = await self.exchange.place_market_sell(symbol, quantity)
        except Exception as e:
            # Handle exchange errors specifically
            error_msg = str(e)
            logger.error(
                f"Error placing market sell order for {symbol}: {error_msg}",
                symbol=symbol,
                quantity=quantity,
                error=error_msg
            )

            # Check if this is an insufficient balance error
            if "insufficient balance" in error_msg.lower():
                # Send notification about the issue
                from src.utils.telegram_utils import send_telegram_message
                await send_telegram_message(
                    f"🔴 Exchange error in place_market_sell: {error_msg}\n"
                    f"Symbol: {symbol}\n"
                    f"Quantity: {quantity} {base_currency}\n"
                    f"Please check your exchange account."
                )

                # Mark position with error
                self.active_trades[symbol]["close_error"] = "exchange_error"
                self.active_trades[symbol]["close_attempts"] = self.active_trades[symbol].get("close_attempts", 0) + 1

                # If too many attempts, remove from active trades
                if self.active_trades[symbol].get("close_attempts", 0) > 5:
                    logger.warning(f"Too many failed attempts to close {symbol}, removing from active trades")
                    del self.active_trades[symbol]

                await self._update_trades_status()

                # Return a special result indicating position was not closed due to exchange error
                return {
                    "symbol": symbol,
                    "entry_price": entry_price,
                    "exit_price": 0,
                    "quantity": 0,
                    "profit": 0,
                    "close_reason": "exchange_error",
                    "order_id": None,
                    "retry": True
                }

            # For other errors, just return empty dict to indicate failure
            return {}

        # Validate execution details
        actual_exit_price = order_result.get("average_price")
        # filled_sell_qty = order_result.get("filled_quantity") # Could verify if needed
        order_id = order_result.get("order_id")

        if actual_exit_price is None:
            logger.error(
                f"Failed to close position for {symbol}: Invalid execution details from sell order.",
                symbol=symbol,
                quantity=quantity,
                order_result=order_result,
            )
            # Position might still be open, or partially closed. Requires complex handling.
            # For now, we assume it failed and don't remove from active_trades yet.
            return {}  # Indicate failure

        # Calculate profit/loss using actual prices
        pnl = 0.0
        if entry_price != 0:
            pnl = ((actual_exit_price - entry_price) / entry_price) * 100
        else:
            logger.warning(
                f"Entry price for {symbol} was 0, cannot calculate PnL percentage.",
                symbol=symbol,
            )

        logger.info(
            f"Position closing for {symbol}",
            symbol=symbol,
            entry_price=entry_price,
            exit_price=actual_exit_price,
            profit=f"{pnl:.2f}%",
            close_reason=close_reason,
            order_id=order_id,
        )

        # Save completed trade using actual exit price
        self.monitor.save_completed_trade(
            {
                "symbol": symbol,
                "entry_price": entry_price,
                "exit_price": actual_exit_price,
                "quantity": quantity,  # Assumes full quantity was sold
                "profit": pnl,
                "entry_time": trade.get(
                    "entry_time", datetime.now().isoformat()
                ),
                "close_reason": close_reason,
                "buy_order_id": trade.get("order_id"),  # Include buy order id
                "sell_order_id": order_id,  # Include sell order id
            }
        )

        # Remove from active trades ONLY after successful close and recording
        del self.active_trades[symbol]

        # Update active trades status in monitor
        await self._update_trades_status()

        logger.info(
            f"Position successfully closed for {symbol}",
            symbol=symbol,
            order_id=order_id,
            profit=f"{pnl:.2f}%",
            remaining_positions=len(self.active_trades),
        )

        # Return actual details
        return {
            "symbol": symbol,
            "entry_price": entry_price,
            "exit_price": actual_exit_price,
            "quantity": quantity,
            "profit": pnl,
            "close_reason": close_reason,
            "order_id": order_id,
        }

    @handle_strategy_errors(notify=True)
    async def _check_and_apply_take_profit(self, symbol: str, current_price: float) -> Dict[str, Any]:
        """
        Check and apply take profit levels for a position
        
        Args:
            symbol: Trading pair symbol
            current_price: Current market price
            
        Returns:
            Dict with take profit execution details or None if no TP triggered
        """
        try:
            if symbol not in self.active_trades:
                return None
                
            trade = self.active_trades[symbol]
            entry_price = trade.get('entry_price', 0)
            
            if entry_price <= 0:
                return None
                
            # Calculate current profit percentage
            current_profit = (current_price - entry_price) / entry_price
            
            # Get take profit levels from config
            tp_levels = self.config.get('take_profit_levels', [])
            if not tp_levels:
                return None
                
            # Sort TP levels by profit target (ascending)
            tp_levels = sorted(tp_levels, key=lambda x: x.get('profit_target', 0))
            
            # Find the highest TP level that hasn't been triggered yet
            for level in tp_levels:
                if not all(k in level for k in ['profit_target', 'percentage']):
                    logger.warning(f"Invalid TP level config: {level}")
                    continue
                    
                level_id = f"tp_{int(level['profit_target'] * 100)}%"
                
                # Skip if this TP level was already triggered
                if level_id in trade.get('triggered_tp_levels', []):
                    continue
                    
                # Check if current profit meets or exceeds this TP level
                if current_profit >= level['profit_target']:
                    # Calculate quantity to sell at this level
                    total_quantity = trade.get('quantity', 0)
                    sell_quantity = total_quantity * level['percentage']
                    
                    if sell_quantity <= 0:
                        continue
                        
                    try:
                        # Execute sell order for this TP level
                        order = await self.exchange.create_market_sell_order(
                            symbol=symbol,
                            amount=sell_quantity,
                            params={'reduceOnly': True}
                        )
                        
                        if order and order.get('status') == 'filled':
                            filled_qty = float(order.get('filled', 0))
                            if filled_qty <= 0:
                                logger.warning(f"TP order filled with zero quantity for {symbol}")
                                continue
                            
                            # Update position quantity
                            trade['quantity'] -= filled_qty
                            
                            # Mark this TP level as triggered
                            if 'triggered_tp_levels' not in trade:
                                trade['triggered_tp_levels'] = []
                            trade['triggered_tp_levels'].append(level_id)
                            
                            # Calculate realized profit
                            realized_profit = (current_price - entry_price) * filled_qty
                            remaining_qty = trade['quantity']
                            
                            logger.info(
                                f"Take profit {level_id} triggered for {symbol}",
                                symbol=symbol,
                                level=level_id,
                                price=current_price,
                                quantity=filled_qty,
                                realized_profit=realized_profit,
                                remaining_quantity=remaining_qty
                            )
                            
                            # Return TP execution details
                            return {
                                'symbol': symbol,
                                'level': level_id,
                                'price': current_price,
                                'quantity': filled_qty,
                                'realized_profit': realized_profit,
                                'remaining_quantity': remaining_qty
                            }
                            
                    except Exception as e:
                        logger.error(f"Error executing take profit for {symbol} at {level_id}: {str(e)}", exc_info=True)
                        continue
                        
        except Exception as e:
            logger.error(f"Error in _check_and_apply_take_profit for {symbol}: {str(e)}", exc_info=True)
                    
        return None
        
    @handle_strategy_errors(notify=True)
    async def check_positions(self, strategy) -> List[Dict[str, Any]]:
        """Check all open positions for exit conditions (SL, TP, Trailing SL, Strategy Signal)"""
        closed_positions = []
        position_count = len(self.active_trades)

        if position_count == 0:
            logger.info("No active positions to check")
            return []
            
        # Check for DCA opportunities first before checking exit conditions
        if self.config.get('dca', {}).get('enabled', False):
            for symbol in list(self.active_trades.keys()):
                try:
                    ticker = await self.exchange.exchange.fetch_ticker(symbol)
                    current_price = ticker.get('last', 0)
                    if current_price > 0:
                        dca_applied = await self._check_and_apply_dca(symbol, current_price)
                        if dca_applied:
                            # If DCA was applied, refresh the ticker data before proceeding
                            await asyncio.sleep(1)  # Small delay to ensure order is processed
                            ticker = await self.exchange.exchange.fetch_ticker(symbol)
                            current_price = ticker.get('last', current_price)
                except Exception as e:
                    logger.error(f"Error checking DCA for {symbol}: {str(e)}", exc_info=True)
                    continue
        
        # Check for take profit levels for all active positions
        active_symbols = list(self.active_trades.keys())
        for symbol in active_symbols:
            try:
                if symbol not in self.active_trades:  # Skip if position was closed in previous iterations
                    continue
                    
                ticker = await self.exchange.exchange.fetch_ticker(symbol)
                current_price = ticker.get('last', 0)
                if current_price <= 0:
                    logger.warning(f"Invalid price for {symbol}: {current_price}")
                    continue
                
                # Check and apply take profit levels
                if self.config.get('take_profit_levels'):
                    tp_result = await self._check_and_apply_take_profit(symbol, current_price)
                    if tp_result and tp_result.get('remaining_quantity', 0) <= 0:
                        # Remove position if fully closed by take profit
                        self.active_trades.pop(symbol, None)
                        continue  # Skip to next symbol as this position is closed
                        
            except Exception as e:
                logger.error(f"Error processing take profit for {symbol}: {str(e)}", exc_info=True)
                continue

        # Get excluded symbols from config
        excluded_symbols = self.config.get("excluded_symbols", [])
        
        # Filter out positions with zero quantity
        active_symbols = [s for s, t in self.active_trades.items() if t.get('quantity', 0) > 0]
        position_count = len(active_symbols)
        
        if position_count == 0:
            return []
            
        logger.info(f"Checking {position_count} active positions: {active_symbols}")

        # Get trading config once
        trailing_stop_enabled = self.config.get("trailing_stop_enabled", False)
        tsl_pct = self.config.get("trailing_stop_pct", 0.01)
        tsl_activation_pct = self.config.get("trailing_stop_activation_pct", 0.01)
        disable_stop_loss = self.config.get("disable_stop_loss", False)
        min_profit_pct = self.config.get("min_profit_pct", 0.03)
        auto_reinvest = self.config.get('auto_reinvest', {})
        
        for symbol, trade in list(self.active_trades.items()):
            if symbol in excluded_symbols:
                logger.info(f"Skipping excluded symbol {symbol}")
                continue
                
            try:
                # TODO: Make timeframe configurable or use shortest from pair_config
                df = await self.exchange.fetch_ohlcv(
                    symbol, timeframe="15m", limit=60
                )
                if df.empty:
                    logger.warning(
                        f"Empty data for {symbol}, skipping position check",
                        symbol=symbol,
                    )
                    continue

                current_price = df["close"].iloc[-1]

                # --- Trailing Stop Logic --- START ---
                entry_price = trade["entry_price"]
                current_stop_loss = trade.get("stop_loss", 0)
                new_stop_loss = current_stop_loss # Start with current SL
                trailing_stop_updated = False

                if trailing_stop_enabled and entry_price > 0 and current_price > entry_price:
                    # Calculate activation price
                    activation_price = entry_price * (1 + tsl_activation_pct)

                    if current_price >= activation_price:
                        # Calculate potential new stop loss based on current price
                        potential_new_sl = current_price * (1 - tsl_pct)

                        # Update SL only if the new potential SL is higher than the current one
                        if potential_new_sl > current_stop_loss:
                            new_stop_loss = potential_new_sl
                            trade["stop_loss"] = new_stop_loss # Update in the trade dict
                            trailing_stop_updated = True
                            logger.info(
                                f"Trailing Stop Loss updated for {symbol}",
                                symbol=symbol,
                                previous_sl=current_stop_loss,
                                new_sl=new_stop_loss,
                                current_price=current_price,
                            )
                # --- Trailing Stop Logic --- END ---

                # Calculate indicators needed for strategy exit signal
                df = strategy.calculate_indicators(df)

                # Check strategy for exit signal
                should_sell, confidence = strategy.should_sell(df)

                logger.info(
                    f"Position check for {symbol}",
                    symbol=symbol,
                    current_price=current_price,
                    entry_price=entry_price,
                    pnl=f"{((current_price - entry_price) / entry_price) * 100:.2f}%",
                    stop_loss_level=trade.get("stop_loss", 0), # Log the actual SL being checked
                    take_profit_level=trade.get("take_profit", 0),
                    trailing_stop_updated_this_cycle=trailing_stop_updated,
                    should_sell_signal=should_sell,
                    stop_loss_triggered=current_price <= trade.get("stop_loss", 0),
                    take_profit_triggered=current_price >= trade.get("take_profit", 0),
                    take_profit_pct=self.config.get("take_profit_pct", 0.03),
                )

                # If take_profit_price is not set or 0, calculate it based on config
                if trade.get("take_profit", 0) == 0 and entry_price > 0:
                    take_profit_pct = self.config.get("take_profit_pct", 0.03)  # Default 3%
                    take_profit_price = entry_price * (1 + take_profit_pct)
                    logger.info(
                        f"Setting missing take_profit_price for {symbol}",
                        symbol=symbol,
                        entry_price=entry_price,
                        take_profit_pct=take_profit_pct,
                        take_profit_price=take_profit_price
                    )
                    # Update the trade with the calculated take_profit_price
                    trade["take_profit"] = take_profit_price

                # Check if stop loss is disabled in config
                disable_stop_loss = self.config.get("disable_stop_loss", False)
                min_profit_pct = self.config.get("min_profit_pct", 0.03)  # Default 3%
                
                # Handle stop loss configuration
                if disable_stop_loss:
                    # If stop loss is disabled, ensure it's set to 0
                    if trade.get("stop_loss", 0) > 0:
                        logger.info(
                            f"Stop loss disabled in config, removing stop_loss for {symbol}",
                            symbol=symbol
                        )
                        trade["stop_loss"] = 0
                elif trade.get("stop_loss", 0) == 0 and entry_price > 0:
                    # If stop loss is not set and not disabled, calculate it
                    stop_loss_pct = self.config.get("stop_loss_pct", 0.02)  # Default 2%
                    stop_loss_price = entry_price * (1 - stop_loss_pct)
                    logger.info(
                        f"Setting stop_loss for {symbol}",
                        symbol=symbol,
                        entry_price=entry_price,
                        stop_loss_pct=stop_loss_pct,
                        stop_loss_price=stop_loss_price
                    )
                    trade["stop_loss"] = stop_loss_price

                # Calculate current profit percentage
                current_profit_pct = ((current_price / entry_price) - 1) if entry_price > 0 else 0
                
                # Check if we should auto-reinvest profits
                if (auto_reinvest.get('enabled', False) and 
                    current_profit_pct >= auto_reinvest.get('min_profit_to_reinvest', 0.02) and
                    trade.get('reinvest_count', 0) < auto_reinvest.get('max_reinvest_times', 3)):
                    
                    # Calculate profit amount to reinvest
                    profit_amount = (current_price - entry_price) * trade.get('quantity', 0)
                    reinvest_amount = profit_amount * auto_reinvest.get('reinvest_percentage', 0.5)
                    
                    if reinvest_amount > 0:
                        try:
                            # Sell portion to realize profit
                            sell_quantity = (reinvest_amount / current_price) * 0.99  # 1% buffer for fees
                            try:
                                order = await self.exchange.create_market_sell_order(
                                    symbol=symbol,
                                    amount=sell_quantity,
                                    params={'reduceOnly': True}
                                )
                            except Exception as e:
                                logger.error(f"Error creating sell order for auto-reinvest: {str(e)}")
                                order = None
                            
                            if order and order.get('status') == 'filled':
                                # Update position
                                trade['quantity'] -= float(order['filled'])
                                trade['reinvest_count'] = trade.get('reinvest_count', 0) + 1
                                
                                logger.info(
                                    f"Auto-reinvested {order['filled']} {symbol} at {current_price}",
                                    symbol=symbol,
                                    amount=float(order['filled']),
                                    price=current_price,
                                    reinvest_count=trade['reinvest_count']
                                )
                                
                                # Update entry price for remaining position
                                trade['entry_price'] = (
                                    (trade.get('entry_price', 0) * trade.get('quantity', 0)) + 
                                    (current_price * float(order['filled']))
                                ) / (trade.get('quantity', 0) + float(order['filled']))
                                
                                # Update position quantity
                                trade['quantity'] += float(order['filled'])
                                
                        except Exception as e:
                            logger.error(f"Error during auto-reinvest for {symbol}: {str(e)}")

                # Initialize close reason
                close_reason = None

                # Determine trigger conditions
                stop_loss_triggered = False
                take_profit_triggered = False

                # Check stop loss condition (only if not disabled)
                if not disable_stop_loss and trade.get("stop_loss", 0) > 0:
                    if current_price <= trade["stop_loss"]:
                        stop_loss_triggered = True
                        close_reason = "stop_loss"
                        logger.info(
                            f"Stop loss triggered for {symbol}",
                            symbol=symbol,
                            current_price=current_price,
                            stop_loss=trade["stop_loss"],
                            pnl=f"{current_profit_pct:.2%}"
                        )
                else:
                    logger.debug(
                        f"Stop loss check skipped for {symbol} - {'disabled' if disable_stop_loss else 'not set'}",
                        symbol=symbol,
                        disable_stop_loss=disable_stop_loss,
                        has_stop_loss=trade.get("stop_loss", 0) > 0
                    )

                # Check take profit condition
                if not stop_loss_triggered:  # Only check TP if SL not triggered
                    if disable_stop_loss:
                        # When stop loss is disabled, use min profit target
                        if current_profit_pct >= min_profit_pct:
                            take_profit_triggered = True
                            close_reason = "min_profit"
                            logger.info(
                                f"Min profit target reached for {symbol}",
                                symbol=symbol,
                                current_price=current_price,
                                entry_price=entry_price,
                                profit_pct=f"{current_profit_pct:.2%}",
                                min_profit_pct=f"{min_profit_pct:.2%}"
                            )
                    elif trade.get("take_profit", 0) > 0 and current_price >= trade["take_profit"]:
                        take_profit_triggered = True
                        close_reason = "take_profit"
                        logger.info(
                            f"Take profit triggered for {symbol}",
                            symbol=symbol,
                            current_price=current_price,
                            take_profit=trade["take_profit"],
                            pnl=f"{current_profit_pct:.2%}"
                        )

                # Check minimum hold time
                min_hold_minutes = self.config.get("hold_time_minutes", 0)
                entry_time = datetime.fromisoformat(trade.get("entry_time", datetime.now().isoformat()))
                hold_time_minutes = (datetime.now() - entry_time).total_seconds() / 60
                
                # Close if TP/SL (potentially trailed) or strategy signal triggered
                if (should_sell or stop_loss_triggered or take_profit_triggered) and \
                   (hold_time_minutes >= min_hold_minutes or stop_loss_triggered):
                    # Ensure we have a close reason
                    if not close_reason:
                        if should_sell:
                            close_reason = "signal"
                        elif stop_loss_triggered:
                            close_reason = "stop_loss"
                        elif take_profit_triggered:
                            close_reason = "min_profit" if disable_stop_loss else "take_profit"
                        else:
                            close_reason = "unknown"
                    
                    # Log hold time information
                    logger.info(
                        f"Hold time check for {symbol}",
                        symbol=symbol,
                        hold_time_minutes=round(hold_time_minutes, 2),
                        min_hold_minutes=min_hold_minutes,
                        can_close=hold_time_minutes >= min_hold_minutes,
                        close_reason=close_reason
                    )
                elif should_sell or take_profit_triggered:  # Log why position wasn't closed
                    logger.info(
                        f"Position for {symbol} not closed - minimum hold time not met",
                        symbol=symbol,
                        hold_time_minutes=round(hold_time_minutes, 2),
                        min_hold_minutes=min_hold_minutes,
                        close_reason="hold_time"
                    )
                    continue

                    # Log the close action with details
                    logger.info(
                        f"Closing {symbol} position - Reason: {close_reason}",
                        symbol=symbol,
                        entry_price=entry_price,
                        current_price=current_price,
                        profit_pct=f"{current_profit_pct:.2%}",
                        stop_loss_triggered=stop_loss_triggered,
                        take_profit_triggered=take_profit_triggered,
                        should_sell=should_sell,
                        trailing_stop_updated=trailing_stop_updated
                    )

                    # Execute the close position
                    result = await self.close_position(
                        symbol, close_reason=close_reason
                    )
                    if result:
                        closed_positions.append(result)
            except Exception as e:
                logger.error(
                    f"Error checking position for {symbol}",
                    symbol=symbol,
                    error=str(e),
                    exc_info=True,
                )

        return closed_positions

    @handle_exchange_errors(notify=False)
    async def _update_trades_status(self) -> None:
        """Update active trades status in monitor using actual entry price"""
        trades_info = []

        for symbol, trade in self.active_trades.items():
            try:
                current_price = await self.exchange.get_current_price(symbol)
                entry_price = trade["entry_price"]  # Uses actual stored entry price
                pnl = 0.0
                if entry_price != 0:
                    pnl = ((current_price - entry_price) / entry_price) * 100
                else:
                    logger.warning(
                        f"Entry price for {symbol} in active_trades is 0, PnL calculation skipped.",
                        symbol=symbol,
                    )

                trades_info.append(
                    {
                        "symbol": symbol,
                        "entry_price": entry_price,
                        "current_price": current_price,
                        "quantity": trade["quantity"],
                        "pnl": pnl,
                    }
                )
            except Exception as e:
                logger.error(
                    f"Error updating trade status for {symbol}",
                    symbol=symbol,
                    error=str(e),
                )

        if trades_info:
            self.monitor.update_trades(trades_info)
            logger.debug(
                f"Updated status for {len(trades_info)} active trades"
            )

    async def cancel_all_orders(self) -> None:
        """Cancel all open orders"""
        try:
            for symbol in self.active_trades.keys():
                try:
                    open_orders = await self.exchange.fetch_open_orders(symbol)
                    for order in open_orders:
                        await self.exchange.cancel_order(order["id"], symbol)
                        logger.info(
                            f"Cancelled order {order['id']} for {symbol}"
                        )
                except Exception as e:
                    logger.error(f"Error cancelling orders for {symbol}: {e}")

        except Exception as e:
            logger.error(f"Error cancelling all orders: {e}")

    async def get_position_summary(self) -> Dict[str, Any]:
        """Get summary of all positions using actual entry prices"""
        try:
            total_value = 0
            total_pnl_value = 0  # Accumulate PnL value (PnL * value)

            for symbol, trade in self.active_trades.items():
                current_price = await self.exchange.get_current_price(symbol)
                entry_price = trade["entry_price"]  # Uses actual stored entry price
                quantity = trade["quantity"]

                position_value = current_price * quantity
                position_pnl_pct = 0.0
                if entry_price != 0:
                    position_pnl_pct = (
                        (current_price - entry_price) / entry_price
                    ) * 100
                else:
                    logger.warning(
                        f"Entry price for {symbol} in active_trades is 0 for summary.",
                        symbol=symbol,
                    )

                # PnL contribution = PnL % * Position Value
                position_pnl_value = (
                    (position_pnl_pct / 100) * (entry_price * quantity)
                    if entry_price != 0
                    else 0
                )
                # Alternative: PnL value = (current_price - entry_price) * quantity
                # position_pnl_value = (current_price - entry_price) * quantity

                total_value += position_value
                total_pnl_value += position_pnl_value  # Sum of PnL in quote currency

            # Calculate overall PnL percentage based on initial total cost
            initial_total_cost = sum(
                t["entry_price"] * t["quantity"]
                for t in self.active_trades.values()
                if t.get("entry_price") and t.get("quantity")
            )
            overall_pnl_pct = (
                (total_pnl_value / initial_total_cost) * 100
                if initial_total_cost > 0
                else 0
            )

            return {
                "total_positions": len(self.active_trades),
                "total_value_current": total_value,
                "initial_total_cost": initial_total_cost,
                "total_pnl_value": total_pnl_value,
                "overall_pnl_percentage": overall_pnl_pct,
            }

        except Exception as e:
            logger.error(f"Error getting position summary: {e}", exc_info=True)
            return {  # Return structure consistent on error
                "total_positions": len(self.active_trades),  # Still know the count
                "total_value_current": 0,
                "initial_total_cost": 0,
                "total_pnl_value": 0,
                "overall_pnl_percentage": 0,
            }

    async def graceful_shutdown(self) -> None:
        """Save active trades using actual entry price during shutdown"""
        try:
            if not self.active_trades:
                return

            logger.warning(
                f"Saving {len(self.active_trades)} active trades during shutdown"
            )

            for symbol, trade in list(self.active_trades.items()):  # Iterate over copy
                try:
                    current_price = await self.exchange.get_current_price(symbol)
                    entry_price = trade["entry_price"]  # Uses actual stored entry price
                    quantity = trade["quantity"]

                    pnl = 0.0
                    if entry_price != 0:
                        pnl = ((current_price - entry_price) / entry_price) * 100
                    else:
                        logger.warning(
                            f"Entry price for {symbol} was 0 during shutdown save.",
                            symbol=symbol,
                        )

                    # Save to completed trades
                    self.monitor.save_completed_trade(
                        {
                            "symbol": symbol,
                            "entry_price": entry_price,
                            "exit_price": current_price,  # Use current price as exit
                            "quantity": quantity,
                            "profit": pnl,
                            "entry_time": trade.get(
                                "entry_time", datetime.now().isoformat()
                            ),
                            "close_reason": "bot_shutdown",
                            "buy_order_id": trade.get("order_id"),
                            "sell_order_id": None,  # No sell order during shutdown save
                        }
                    )
                    # Optionally remove from active_trades here if desired,
                    # but maybe not necessary if process is ending anyway.
                    # del self.active_trades[symbol]

                except Exception as e:
                    logger.error(
                        f"Error saving trade for {symbol} during shutdown: {e}",
                        symbol=symbol,
                        exc_info=True,  # Add exc_info
                    )

        except Exception as e:
            logger.error(f"Error during position manager shutdown: {e}")
