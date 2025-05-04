"""
Position and trade management
"""
import logging
from datetime import datetime
from typing import Dict, Any, Tuple, List, Optional

from src.utils.status_monitor import BotStatusMonitor
from src.exchange.connector import ExchangeConnector

logger = logging.getLogger(__name__)

class PositionManager:
    """Manages trading positions, entry/exit, and trade tracking"""
    
    def __init__(
        self, 
        exchange: ExchangeConnector,
        trading_config: Dict[str, Any],
        monitor: BotStatusMonitor
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
        
    async def open_position(
        self, 
        symbol: str, 
        quantity: float,
        entry_price: float,
        risk_level: Dict[str, float],
        confidence: float,
        pair_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Open a new position
        
        Args:
            symbol: Trading pair symbol
            quantity: Position size
            entry_price: Entry price
            risk_level: Stop loss and take profit levels
            confidence: Trade confidence (0-1)
            pair_config: Trading pair configuration
            
        Returns:
            New position information
        """
        try:
            # Place market buy order
            order = await self.exchange.place_market_buy(symbol, quantity)
            
            # Record trade
            self.active_trades[symbol] = {
                'entry_price': entry_price,
                'quantity': quantity,
                'entry_time': datetime.now().isoformat(),
                'stop_loss': risk_level.get('stop_loss', 0),
                'take_profit': risk_level.get('take_profit', 0),
                'confidence': confidence
            }
            
            # Update active trades in monitor
            await self._update_trades_status()
            
            return {
                'symbol': symbol,
                'entry_price': entry_price,
                'quantity': quantity,
                'risk_level': risk_level
            }
            
        except Exception as e:
            logger.error(f"Error opening position for {symbol}: {e}")
            raise
            
    async def close_position(
        self, 
        symbol: str, 
        exit_price: float,
        close_reason: str
    ) -> Dict[str, Any]:
        """Close an existing position
        
        Args:
            symbol: Trading pair symbol
            exit_price: Exit price
            close_reason: Reason for closing (take_profit, stop_loss, signal, manual)
            
        Returns:
            Closed position information
        """
        try:
            if symbol not in self.active_trades:
                logger.warning(f"Cannot close position for {symbol}: not in active trades")
                return {}
                
            trade = self.active_trades[symbol]
            
            # Place market sell order
            order = await self.exchange.place_market_sell(symbol, trade['quantity'])
            
            # Calculate profit/loss
            entry_price = trade['entry_price']
            pnl = ((exit_price - entry_price) / entry_price) * 100
            
            # Save completed trade
            self.monitor.save_completed_trade({
                'symbol': symbol,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'quantity': trade['quantity'],
                'profit': pnl,
                'entry_time': trade['entry_time'],
                'close_reason': close_reason
            })
            
            # Remove from active trades
            del self.active_trades[symbol]
            
            # Update active trades in monitor
            await self._update_trades_status()
            
            return {
                'symbol': symbol,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'profit': pnl,
                'close_reason': close_reason
            }
            
        except Exception as e:
            logger.error(f"Error closing position for {symbol}: {e}")
            raise
            
    async def check_positions(self, strategy) -> List[Dict[str, Any]]:
        """Check all open positions for exit conditions
        
        Args:
            strategy: Trading strategy
            
        Returns:
            List of closed positions
        """
        closed_positions = []
        
        try:
            for symbol, trade in list(self.active_trades.items()):
                # Get current market data
                df = await self.exchange.fetch_ohlcv(symbol, timeframe='15m', limit=10)
                if df.empty:
                    continue

                current_price = df['close'].iloc[-1]
                
                # Calculate indicators
                df = strategy.calculate_indicators(df)

                # Check if we should sell
                should_sell, confidence = strategy.should_sell(df)
                
                # Check stop loss and take profit
                entry_price = trade['entry_price']
                pnl = ((current_price - entry_price) / entry_price) * 100
                
                stop_loss_triggered = trade.get('stop_loss') > 0 and current_price <= trade['stop_loss']
                take_profit_triggered = trade.get('take_profit') > 0 and current_price >= trade['take_profit']
                
                if should_sell or stop_loss_triggered or take_profit_triggered:
                    close_reason = 'signal' if should_sell else 'stop_loss' if stop_loss_triggered else 'take_profit'
                    
                    # Close position
                    result = await self.close_position(symbol, current_price, close_reason)
                    closed_positions.append(result)
                    
                    logger.info(
                        f"Closed position for {symbol} at {current_price} "
                        f"with {pnl:.2f}% profit/loss. Reason: {close_reason}"
                    )
                    
            return closed_positions
                    
        except Exception as e:
            logger.error(f"Error checking positions: {e}")
            return []
            
    async def _update_trades_status(self) -> None:
        """Update active trades status in monitor"""
        try:
            trades_info = []
            
            for symbol, trade in self.active_trades.items():
                current_price = await self.exchange.get_current_price(symbol)
                entry_price = trade['entry_price']
                pnl = ((current_price - entry_price) / entry_price) * 100
                
                trades_info.append({
                    'symbol': symbol,
                    'entry_price': entry_price,
                    'current_price': current_price,
                    'quantity': trade['quantity'],
                    'pnl': pnl
                })
                
            self.monitor.update_trades(trades_info)
            
        except Exception as e:
            logger.error(f"Error updating trades status: {e}")
            
    async def cancel_all_orders(self) -> None:
        """Cancel all open orders"""
        try:
            for symbol in self.active_trades.keys():
                try:
                    open_orders = await self.exchange.fetch_open_orders(symbol)
                    for order in open_orders:
                        await self.exchange.cancel_order(order['id'], symbol)
                        logger.info(f"Cancelled order {order['id']} for {symbol}")
                except Exception as e:
                    logger.error(f"Error cancelling orders for {symbol}: {e}")
                    
        except Exception as e:
            logger.error(f"Error cancelling all orders: {e}")
            
    async def get_position_summary(self) -> Dict[str, Any]:
        """Get summary of all positions
        
        Returns:
            Summary of positions
        """
        try:
            total_value = 0
            total_pnl = 0
            
            for symbol, trade in self.active_trades.items():
                current_price = await self.exchange.get_current_price(symbol)
                entry_price = trade['entry_price']
                quantity = trade['quantity']
                
                position_value = current_price * quantity
                position_pnl = ((current_price - entry_price) / entry_price) * 100
                
                total_value += position_value
                total_pnl += position_pnl * position_value  # Weighted PnL
            
            # Calculate weighted average PnL
            avg_pnl = total_pnl / total_value if total_value > 0 else 0
            
            return {
                'total_positions': len(self.active_trades),
                'total_value': total_value,
                'average_pnl': avg_pnl
            }
            
        except Exception as e:
            logger.error(f"Error getting position summary: {e}")
            return {
                'total_positions': 0,
                'total_value': 0,
                'average_pnl': 0
            }
            
    def graceful_shutdown(self) -> None:
        """Save active trades to completed trades during shutdown"""
        try:
            if not self.active_trades:
                return
                
            logger.warning(f"Saving {len(self.active_trades)} active trades during shutdown")
            
            for symbol, trade in self.active_trades.items():
                try:
                    current_price = self.exchange.get_current_price(symbol)
                    entry_price = trade['entry_price']
                    pnl = ((current_price - entry_price) / entry_price) * 100
                    
                    # Save to completed trades
                    self.monitor.save_completed_trade({
                        'symbol': symbol,
                        'entry_price': entry_price,
                        'exit_price': current_price,
                        'quantity': trade['quantity'],
                        'profit': pnl,
                        'entry_time': trade.get('entry_time', datetime.now().isoformat()),
                        'close_reason': 'bot_shutdown'
                    })
                    
                except Exception as e:
                    logger.error(f"Error saving trade for {symbol} during shutdown: {e}")
                    
        except Exception as e:
            logger.error(f"Error during position manager shutdown: {e}")
