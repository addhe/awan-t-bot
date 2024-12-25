import ccxt
import os
import logging
import time
import pandas as pd
import numpy as np
import json
import requests
from logging.handlers import RotatingFileHandler
from datetime import datetime, time as dt_time

from config.config import CONFIG
from src.modules.send_telegram_notification import send_telegram_notification
from src.modules.initialize_exchange import initialize_exchange
from src.modules.check_exchange_health import check_exchange_health
from src.modules.cleanup_old_orders import cleanup_old_orders
from src.modules.emergency_stop import emergency_stop

exchange = None

# Add after imports
MIN_CCXT_VERSION = "4.0.0"
try:
    from packaging import version
    print(f"CCXT Version: {ccxt.__version__}")
    if version.parse(ccxt.__version__) < version.parse(MIN_CCXT_VERSION):
        logging.error(f"CCXT version {MIN_CCXT_VERSION} or higher is required")
        exit(1)
except ImportError:
    logging.warning("packaging module not found, skipping version check")

# Logging setup
log_handler = RotatingFileHandler('trade_log.log', maxBytes=5*1024*1024, backupCount=2)
logging.basicConfig(handlers=[log_handler], level=logging.INFO,
                   format='%(asctime)s - %(levelname)s - %(message)s')

# API Configuration
API_KEY = os.environ.get('API_KEY_BINANCE')
API_SECRET = os.environ.get('API_SECRET_BINANCE')

if API_KEY is None or API_SECRET is None:
    logging.error('API credentials not found in environment variables')
    exit(1)

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
            json.dump(self.metrics, f)

    def update_trade(self, profit, won=False):
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
    def calculate_sharpe_ratio(profits, risk_free_rate=0.02):
        if len(profits) < 2:
            return 0
        returns = pd.Series(profits)
        excess_returns = returns - (risk_free_rate / 252)
        if excess_returns.std() == 0:
            return 0
        return np.sqrt(252) * (excess_returns.mean() / excess_returns.std())

    @staticmethod
    def calculate_max_drawdown(profits):
        cumulative = np.cumsum(profits)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = running_max - cumulative
        return np.max(drawdown) if len(drawdown) > 0 else 0

    def can_trade(self):
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


def check_system_health():
    try:
        # Check disk space
        import psutil
        disk_usage = psutil.disk_usage('/')
        if disk_usage.percent > 90:
            logging.warning("Low disk space warning")
            
        # Check memory usage
        memory = psutil.virtual_memory()
        if memory.percent > 90:
            logging.warning("High memory usage warning")
            
        # Check CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        if cpu_percent > 90:
            logging.warning("High CPU usage warning")
            
        return True
    except Exception as e:
        logging.error(f"Error checking system health: {e}")
        return False

def check_signal_quality(df, side, current_idx):
    try:
        # Additional validation criteria example
        if df['volatility'].iloc[current_idx] < 0.02:
            logging.info('Volatility too low, skipping signal')
            return False
        
        # Existing trend consistency checks
        last_candles = 3
        if side == 'buy':
            trend_consistent = all(
                df['close'].iloc[i] > df['ema_short'].iloc[i] 
                for i in range(current_idx-last_candles, current_idx+1)
            )
        else:
            trend_consistent = all(
                df['close'].iloc[i] < df['ema_short'].iloc[i] 
                for i in range(current_idx-last_candles, current_idx+1)
            )
        
        return trend_consistent
    except Exception as e:
        logging.error(f"Error checking signal quality: {e}")
        return False

def manage_position_risk(position_size, market_price, balance):
    try:
        position_value = position_size * market_price
        account_value = balance['USDT']['free'] + balance['USDT']['used']  # Consider margin
        risk_ratio = position_value / (account_value * CONFIG['leverage'])

        MAX_POSITION_PCT = 0.2  # 20% of account with leverage
        if risk_ratio > MAX_POSITION_PCT:
            new_size = (account_value * MAX_POSITION_PCT * CONFIG['leverage']) / market_price
            logging.warning(f"Reducing position size from {position_size} to {new_size} due to risk limits")
            return new_size

        return position_size
    except Exception as e:
        logging.error(f"Error in position risk management: {e}")
        return position_size

def analyze_trading_performance(performance):
    try:
        metrics = performance.metrics
        
        # Calculate and log key metrics
        performance_summary = {
            'total_trades': metrics['total_trades'],
            'win_rate': metrics.get('win_rate', 0),
            'average_profit': metrics['total_profit'] / max(1, metrics['total_trades']),
            'max_drawdown': metrics['max_drawdown'],
            'sharpe_ratio': metrics.get('sharpe_ratio', 0),
            'daily_pnl': metrics['trade_history'][-10:]  # Log the last 10 trades
        }
        
        logging.info(f"Performance Summary: {json.dumps(performance_summary, indent=2)}")
        return performance_summary
        
    except Exception as e:
        logging.error(f"Error analyzing performance: {e}")
        return None

def monitor_positions(exchange):
    try:
        balance = exchange.fetch_balance()
        positions = exchange.fetch_positions([CONFIG['symbol']])
        max_loss_per_position = balance['USDT']['total'] * CONFIG['max_loss_per_position'] / 100

        for position in positions:
            if float(position['contracts']) != 0:
                entry_price = float(position['entryPrice'])
                current_price = float(position['markPrice'])
                position_size = float(position['contracts'])

                # Calculate current profit/loss
                pnl = (current_price - entry_price) * position_size
                total_fee = position_size * entry_price * CONFIG['fee_rate'] * 2
                actual_pnl = pnl - total_fee

                position_info = (
                    f"Position Monitor:\n"
                    f"Size: {position_size}\n"
                    f"Entry: {entry_price:.2f}\n"
                    f"Current: {current_price:.2f}\n"
                    f"P/L: {actual_pnl:.4f} USDT\n"
                    f"Fees: {total_fee:.4f} USDT"
                )

                logging.info(position_info)
                send_telegram_notification(position_info)

                # Check if exceeding max loss and close the position if needed
                if actual_pnl < -max_loss_per_position:
                    logging.critical("Position exceeded max loss limit, closing position")
                    close_position(exchange, position)
                
    except Exception as e:
        logging.error(f'Error monitoring positions: {e}')

def close_position(exchange, position):
    try:
        symbol = CONFIG['symbol']
        position_size = abs(float(position['contracts']))
        side = 'sell' if position['contracts'] > 0 else 'buy'  # Opened long if contracts > 0, close with sell; vice-versa

        # Place an opposite order to close the position
        order = exchange.create_order(
            symbol=symbol,
            type='market',
            side=side,
            amount=position_size
        )
        logging.info(f"Position closed: {side} {position_size} contracts for {symbol}")
        send_telegram_notification(f"Position closed: {side} {position_size} contracts for {symbol}")

    except Exception as e:
        logging.error(f"Error closing position: {e}")

def assess_risk_conditions(df, balance, exchange):
    try:
        # Define thresholds for reassessment
        increased_volatility_threshold = CONFIG['re_evaluate_volatility_threshold']

        # Check for increased volatility
        if df['volatility'].iloc[-1] > increased_volatility_threshold:
            logging.warning("Increased volatility detected, reassessing positions")
            positions = exchange.fetch_positions([CONFIG['symbol']])
            # If conditions are risky, consider closing or adjusting positions
            for position in positions:
                if float(position['contracts']) != 0:
                    logging.info("Closing position due to adverse market condition")
                    close_position(exchange, position)
                    send_telegram_notification("Closing position due to adverse market condition")

    except Exception as e:
        logging.error(f'Error assessing risk conditions: {e}')

def recover_from_error(exchange, error):
    """Attempt to recover from common errors"""
    try:
        error_msg = str(error).lower()
        
        if 'insufficient balance' in error_msg:
            # Cancel all orders and close positions
            emergency_stop(exchange)
            return True
            
        if 'rate limit' in error_msg:
            time.sleep(60)  # Wait for rate limit to reset
            return True
            
        if 'market closed' in error_msg:
            logging.error("Market is closed")
            return False
            
        if 'leverage not initialized' in error_msg:
            set_leverage(exchange)
            return True
            
        return False
        
    except Exception as e:
        logging.error(f"Error in recovery attempt: {e}")
        return False

def validate_config():
    try:
        required_fields = [
            'symbol', 'leverage', 'risk_percentage', 'min_balance',
            'max_daily_trades', 'max_daily_loss_percent'
        ]
        
        for field in required_fields:
            if field not in CONFIG:
                raise ValueError(f"Missing required config field: {field}")
        
        # Validate numeric values
        if not isinstance(CONFIG['leverage'], (int, float)) or CONFIG['leverage'] <= 0:
            raise ValueError("Invalid leverage value")
            
        if CONFIG['leverage'] > 20:
            raise ValueError("Leverage too high, maximum allowed is 20x")
            
        if CONFIG['risk_percentage'] > 5:
            raise ValueError("Risk percentage too high, maximum allowed is 5%")
            
        if CONFIG['min_balance'] < 0:
            raise ValueError("Min balance cannot be negative")
            
        if CONFIG['timeframe'] not in ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h']:
            raise ValueError("Invalid timeframe")
            
        logging.info("Config validation passed")
        return True
        
    except Exception as e:
        logging.error(f"Config validation failed: {e}")
        return False


def evaluate_signal_strength(df, side, current_idx):
    try:
        signal_strength = 0
        
        # Volume strength
        if df['volume_ratio'].iloc[current_idx] > 1.5:
            signal_strength += 1
        
        # Trend strength
        if side == 'buy':
            if df['close'].iloc[current_idx] > df['ema_short'].iloc[current_idx] > df['ema_long'].iloc[current_idx]:
                signal_strength += 1
        else:
            if df['close'].iloc[current_idx] < df['ema_short'].iloc[current_idx] < df['ema_long'].iloc[current_idx]:
                signal_strength += 1
        
        # RSI confirmation
        if side == 'buy' and df['rsi'].iloc[current_idx] < 30:
            signal_strength += 1
        elif side == 'sell' and df['rsi'].iloc[current_idx] > 70:
            signal_strength += 1
            
        return signal_strength >= 2  # Minimal 2 konfirmasi
        
    except Exception as e:
        logging.error(f"Error evaluating signal strength: {e}")
        return False

def calculate_indicators(df):
    try:
        # Existing indicators
        df['ema_short'] = df['close'].ewm(span=CONFIG['ema_short_period'], adjust=False).mean()
        df['ema_long'] = df['close'].ewm(span=CONFIG['ema_long_period'], adjust=False).mean()
        df['macd'] = df['ema_short'] - df['ema_long']
        df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()

        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        # Volume analysis
        df['volume_ma'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma']

        # Momentum
        df['price_change'] = df['close'].pct_change()
        df['momentum'] = df['price_change'].rolling(window=3).sum()

        # New indicators
        # ATR
        df['tr'] = pd.DataFrame({
            'hl': df['high'] - df['low'],
            'hc': abs(df['high'] - df['close'].shift()),
            'lc': abs(df['low'] - df['close'].shift())
        }).max(axis=1)
        df['atr'] = df['tr'].rolling(window=CONFIG['atr_period']).mean()

        # VWAP
        df['vwap'] = (df['volume'] * df['close']).rolling(window=CONFIG['vwap_period']).sum() / \
                     df['volume'].rolling(window=CONFIG['vwap_period']).sum()

        # Volatility
        df['volatility'] = df['close'].pct_change().rolling(window=20).std() * np.sqrt(365)

        return df
    except Exception as e:
        logging.error(f'Error calculating indicators: {e}')
        raise


def calculate_min_order_size(exchange, symbol, market_price):
    try:
        # Get market info
        market = exchange.market(symbol)
        min_amount = market['limits']['amount']['min']
        min_cost = market.get('limits', {}).get('cost', {}).get('min', 5)  # Default to 5 USDT if not specified

        # Calculate minimum order size based on price
        min_size_by_cost = min_cost / market_price

        # Use the larger of min_amount and min_size_by_cost
        min_order_size = max(min_amount, min_size_by_cost)

        return min_order_size
    except Exception as e:
        logging.error(f'Error calculating minimum order size: {e}')
        return None

def calculate_position_size(balance, entry_price, stop_loss, exchange, volatility):
    try:
        # Risk 0.5% of available balance
        risk_amount = balance['USDT']['free'] * (CONFIG['risk_percentage'] / 100)
        price_distance = abs(entry_price - stop_loss)
        position_size = (risk_amount / price_distance) * CONFIG['leverage']

        min_size = calculate_min_order_size(exchange, CONFIG['symbol'], entry_price)
        if position_size < min_size:
            logging.info(f"Increasing position size to minimum size: {min_size:.8f}")
            position_size = min_size

        max_position = (balance['USDT']['free'] * CONFIG['leverage'] * 0.95) / entry_price
        position_size = min(position_size, max_position)

        return round(position_size, 3)  # Ideally match decimal precision of the symbol
    except Exception as e:
        logging.error(f'Error calculating position size: {e}')
        raise

def validate_order_size(position_size, market_price, balance):
    try:
        order_value = position_size * market_price
        available_balance = balance['USDT']['free']
        required_margin = order_value / CONFIG['leverage']
        
        # Check if order uses more than 20% of available balance
        if required_margin > (available_balance * 0.2):
            logging.warning(f"Order size too large relative to balance. Required margin: {required_margin:.2f} USDT")
            return False
            
        # Check if order value is at least 5 USDT
        if order_value < 5:
            logging.warning(f"Order value too small: {order_value:.2f} USDT")
            return False
            
        return True
    except Exception as e:
        logging.error(f'Error validating order size: {e}')
        return False

def check_market_conditions(df):
    try:
        # current_hour = datetime.now().hour
        # if current_hour in CONFIG['excluded_hours']:
        #     logging.info('Trading not allowed during this hour')
        #     return False

        # Volume check
        current_volume = df['volume'].iloc[-1] * df['close'].iloc[-1]
        if current_volume < CONFIG['min_volume_usdt']:
            logging.info('Insufficient volume')
            return False

        # Volatility check
        if df['volatility'].iloc[-1] > CONFIG['max_volatility_threshold']:
            logging.info('Volatility too high')
            return False

        # ATR check
        if df['atr'].iloc[-1] > CONFIG['max_atr_threshold']:
            logging.info('ATR too high')
            return False

        return True
    except Exception as e:
        logging.error(f'Error checking market conditions: {e}')
        return False


def check_existing_position(exchange, side):
    try:
        positions = exchange.fetch_positions([CONFIG['symbol']])
        for position in positions:
            position_size = float(position['contracts'])
            if position_size != 0:
                position_side = 'long' if position_size > 0 else 'short'
                if (side == 'buy' and position_side == 'short') or \
                   (side == 'sell' and position_side == 'long'):
                    return True
        return False
    except Exception as e:
        logging.error(f'Error checking existing position: {e}')
        return True


def place_order_with_sl_tp(exchange, side, amount, market_price, initial_stop_loss_price, take_profit_price):
    try:
        entry_fee = amount * market_price * CONFIG['fee_rate']
        exit_fee = amount * take_profit_price * CONFIG['fee_rate']
        total_fees = entry_fee + exit_fee

        # Place initial market order
        order = exchange.create_order(
            symbol=CONFIG['symbol'],
            type='market',
            side=side,
            amount=amount,
            params={'reduceOnly': False}
        )

        if order:
            entry_price = float(order['price'])
            logging.info(f"Order Placed: {side.upper()}, Entry Price: {entry_price}")

            # Calculate Take Profit Levels
            tp1_amount = amount * CONFIG['partial_tp_1']
            tp2_amount = amount * CONFIG['partial_tp_2']
            tp1_price = entry_price * (1 + CONFIG['tp1_target']) if side == 'buy' else entry_price * (1 - CONFIG['tp1_target'])
            tp2_price = entry_price * (1 + CONFIG['tp2_target']) if side == 'buy' else entry_price * (1 - CONFIG['tp2_target'])

            # Place Take Profit Orders
            tp1_order = exchange.create_order(
                symbol=CONFIG['symbol'],
                type='TAKE_PROFIT_MARKET',
                side='sell' if side == 'buy' else 'buy',
                amount=tp1_amount,
                params={
                    'stopPrice': tp1_price,
                    'workingType': 'MARK_PRICE',
                    'reduceOnly': True
                }
            )

            tp2_order = exchange.create_order(
                symbol=CONFIG['symbol'],
                type='TAKE_PROFIT_MARKET',
                side='sell' if side == 'buy' else 'buy',
                amount=tp2_amount,
                params={
                    'stopPrice': tp2_price,
                    'workingType': 'MARK_PRICE',
                    'reduceOnly': True
                }
            )

            # Calculate and place the adaptive trailing stop order
            trailing_trigger_price = entry_price * (1 + CONFIG['initial_profit_for_trailing_stop']) if side == 'buy' else entry_price * (1 - CONFIG['initial_profit_for_trailing_stop'])
            if market_price >= trailing_trigger_price:  # Check if initial profit level is reached
                trailing_distance = CONFIG['trailing_distance_pct'] * entry_price
                sl_order = exchange.create_order(
                    symbol=CONFIG['symbol'],
                    type='TRAILING_STOP_MARKET',
                    side='sell' if side == 'buy' else 'buy',
                    amount=amount,
                    params={
                        'activationPrice': trailing_trigger_price,
                        'callbackRate': CONFIG['trailing_distance_pct'] * 100,
                        'workingType': 'MARK_PRICE',
                        'reduceOnly': True
                    }
                )
                logging.info(f"Trailing Stop set to activate at {trailing_trigger_price}")

            order_info = (
                f"New {side.upper()} position opened:\n"
                f"Entry Price: {entry_price:.2f}\n"
                f"Amount: {amount}\n"
                f"TP1: {tp1_price:.2f} ({CONFIG['partial_tp_1']*100}%)\n"
                f"TP2: {tp2_price:.2f} ({CONFIG['partial_tp_2']*100}%)\n"
                f"Adaptive Trailing Stop: {trailing_trigger_price:.2f} if reached\n"
                f"Estimated Fees: {total_fees:.4f} USDT"
            )

            logging.info(order_info)
            send_telegram_notification(order_info)

        return order

    except Exception as e:
        logging.error(f'Failed to place order with TP/SL: {e}')
        return None

def set_leverage(exchange):
    try:
        # Cara baru untuk set leverage menggunakan CCXT
        exchange.set_leverage(CONFIG['leverage'], CONFIG['symbol'])

        # Alternative method jika yang di atas tidak bekerja
        """
        exchange.fapiPrivate_post_leverage({
            'symbol': CONFIG['symbol'].replace('/', ''),
            'leverage': CONFIG['leverage']
        })
        """

        logging.info(f"Leverage set to {CONFIG['leverage']}x")
    except Exception as e:
        # Jika gagal set leverage, coba cara alternatif
        try:
            symbol = CONFIG['symbol'].replace('/', '')
            response = exchange.fapiPrivate_post_leverage({
                'symbol': symbol,
                'leverage': CONFIG['leverage']
            })
            logging.info(f"Leverage set to {CONFIG['leverage']}x using alternative method")
        except Exception as e2:
            try:
                # Cara ketiga menggunakan method spesifik Binance
                response = exchange.private_post_margintype({
                    'symbol': CONFIG['symbol'].replace('/', ''),
                    'marginType': 'ISOLATED'  # atau 'CROSSED' tergantung kebutuhan
                })
                response = exchange.private_post_leverage({
                    'symbol': CONFIG['symbol'].replace('/', ''),
                    'leverage': CONFIG['leverage']
                })
                logging.info(f"Leverage set to {CONFIG['leverage']}x using third method")
            except Exception as e3:
                logging.error(f'All attempts to set leverage failed: {str(e3)}')
                raise Exception("Unable to set leverage")

def check_funding_rate(exchange, intended_side=None):
    try:
        funding_rate = exchange.fetch_funding_rate(CONFIG['symbol'])
        current_rate = funding_rate['fundingRate']
        next_funding = funding_rate['fundingTimestamp']
        current_time = exchange.milliseconds()

        logging.info(f'Current Funding Rate: {current_rate:.6f}')

        # Check if near funding time
        if abs(next_funding - current_time) < 5 * 60 * 1000:
            logging.info('Skipping trade: Near funding time')
            return False

        if intended_side:
            if intended_side == 'buy' and current_rate > CONFIG['funding_rate_threshold']:
                logging.info('Skipping LONG: Unfavorable funding rate')
                return False
            elif intended_side == 'sell' and current_rate < -CONFIG['funding_rate_threshold']:
                logging.info('Skipping SHORT: Unfavorable funding rate')
                return False
        else:
            # If no intended side, use original threshold check
            if abs(current_rate) > CONFIG['funding_rate_threshold']:
                logging.info('Skipping trade: Funding rate outside threshold')
                return False

        logging.info('Funding rate check passed')
        return True

    except Exception as e:
        logging.error(f'Error checking funding rate: {e}')
        return False


def fetch_ohlcv(exchange, symbol, limit=50, timeframe='1m'):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        if ohlcv and len(ohlcv) > 0:
            return ohlcv
        else:
            logging.error('Empty OHLCV data received')
            return None
    except ccxt.NetworkError as e:
        logging.error(f"Network error while fetching OHLCV data: {str(e)}")
        return
    except Exception as e:
        logging.error(f"Unexpected error while fetching OHLCV data: {str(e)}")
        return
    except Exception as e:
        logging.error(f'Failed to fetch OHLCV data: {e}')
        return None

def calculate_dynamic_stop_loss(df, side, market_price):
    atr = df['atr'].iloc[-1]
    if side == 'buy':
        return market_price - (atr * 1.5)  # Tighter stop based on strategy
    return market_price + (atr * 1.5)

def check_market_health(df):
    try:
        # Trend strength
        ema_50 = df['close'].ewm(span=50, adjust=False).mean()
        ema_200 = df['close'].ewm(span=200, adjust=False).mean()

        # Market trend
        is_uptrend = ema_50.iloc[-1] > ema_200.iloc[-1]
        price_above_ema = df['close'].iloc[-1] > ema_50.iloc[-1]

        # Volume trend
        avg_volume = df['volume'].mean()
        current_volume = df['volume'].iloc[-1]
        good_volume = current_volume > avg_volume

        return {
            'is_uptrend': is_uptrend,
            'price_above_ema': price_above_ema,
            'good_volume': good_volume
        }
    except Exception as e:
        logging.error(f'Error checking market health: {e}')
        return None

def limit_position_size(size, market_price, balance):
    max_position_value = balance['USDT']['free'] * CONFIG['leverage'] * 0.95  # 95% of available leverage
    max_size = max_position_value / market_price
    return min(size, max_size)

def check_risk_limits(performance):
    daily_loss_limit = CONFIG['max_daily_loss_percent'] / 100
    max_drawdown_limit = CONFIG['max_drawdown_percent'] / 100
    
    if performance.metrics['daily_loss'] >= daily_loss_limit:
        logging.warning(f"Daily loss limit reached: {performance.metrics['daily_loss']*100:.2f}%")
        return False
        
    if performance.metrics['max_drawdown'] >= max_drawdown_limit:
        logging.warning(f"Max drawdown limit reached: {performance.metrics['max_drawdown']*100:.2f}%")
        return False
        
    return True


def log_market_conditions(df, market_health, market_data):
    try:
        market_info = {
            'current_time': datetime.now().isoformat(),
            'price': df['close'].iloc[-1],
            'volume': df['volume'].iloc[-1],
            'rsi': df['rsi'].iloc[-1],
            'macd': df['macd'].iloc[-1],
            'signal': df['signal'].iloc[-1],
            'volatility': df['volatility'].iloc[-1],
            'atr': df['atr'].iloc[-1],
            'trend': 'uptrend' if market_health['is_uptrend'] else 'downtrend',
            'volume_quality': 'good' if market_health['good_volume'] else 'poor',
            'support': market_data['support'],
            'resistance': market_data['resistance']
        }
        logging.info(f"Market Conditions: {json.dumps(market_info, indent=2)}")
    except Exception as e:
        logging.error(f'Error logging market conditions: {e}')


def validate_position_size(position_size, market_price, balance, min_order_size):
    try:
        if position_size < min_order_size:
            logging.info(f"Position size ({position_size:.8f}) below minimum ({min_order_size:.8f})")
            return False
            
        order_value = position_size * market_price
        available_balance = balance['USDT']['free']
        required_margin = order_value / CONFIG['leverage']
        
        if required_margin > (available_balance * 0.2):
            logging.warning(f"Order size too large. Required margin: {required_margin:.2f} USDT")
            return False
            
        if order_value < 5:
            logging.warning(f"Order value too small: {order_value:.2f} USDT")
            return False
            
        return True
    except Exception as e:
        logging.error(f'Error validating position size: {e}')
        return False

def handle_order_error(e, side, amount):
    error_msg = str(e)
    if 'insufficient balance' in error_msg.lower():
        logging.error(f"Insufficient balance for {side} order of {amount}")
    elif 'minimum notional' in error_msg.lower():
        logging.error(f"Order amount too small: {amount}")
    else:
        logging.error(f"Unknown order error: {error_msg}")

def update_performance_metrics(performance, trade_result):
    try:
        performance.metrics['trade_history'].append({
            'timestamp': datetime.now().isoformat(),
            'profit': trade_result['profit'],
            'side': trade_result['side'],
            'entry_price': trade_result['entry_price'],
            'exit_price': trade_result.get('exit_price', None),
            'position_size': trade_result['position_size'],
            'duration': trade_result.get('duration', None),
            'fees': trade_result['fees']
        })
        performance.save_metrics()
    except Exception as e:
        logging.error(f'Error updating performance metrics: {e}')

def update_market_data(df):
    # Calculate support and resistance
    pivot = (df['high'].iloc[-1] + df['low'].iloc[-1] + df['close'].iloc[-1]) / 3
    support = 2 * pivot - df['high'].iloc[-1]
    resistance = 2 * pivot - df['low'].iloc[-1]
    
    return {
        'support': support,
        'resistance': resistance,
        'pivot': pivot
    }

def analyze_market_depth(exchange, symbol, side):
    try:
        orderbook = exchange.fetch_order_book(symbol)
        bids = orderbook['bids']
        asks = orderbook['asks']
        
        bid_volume = sum(bid[1] for bid in bids[:5])
        ask_volume = sum(ask[1] for ask in asks[:5])
        
        imbalance = bid_volume / ask_volume if ask_volume > 0 else float('inf')
        
        logging.info(f"Order book imbalance: {imbalance:.2f} (bid/ask ratio)")
        
        if side == 'buy' and imbalance < 0.8:
            logging.info(f"Unfavorable buy-side liquidity: {imbalance:.2f}")
            return False
        elif side == 'sell' and imbalance > 1.2:
            logging.info(f"Unfavorable sell-side liquidity: {imbalance:.2f}")
            return False
            
        return True
    except Exception as e:
        logging.error(f"Error analyzing market depth: {e}")
        return True

def handle_exchange_error(e, retry_count=0):
    error_msg = str(e).lower()
    
    if 'rate limit' in error_msg:
        sleep_time = (2 ** retry_count) * 10
        logging.warning(f"Rate limit hit, sleeping for {sleep_time} seconds")
        time.sleep(sleep_time)
        return True
        
    if 'insufficient balance' in error_msg:
        logging.error("Insufficient balance error")
        return False
        
    if 'market is closed' in error_msg:
        logging.error("Market is closed")
        return False
        
    if 'invalid nonce' in error_msg:
        logging.error("Time synchronization error")
        return False
        
    logging.error(f"Unknown exchange error: {error_msg}")
    return False

def check_trend_strength(df):
    try:
        # Calculate ADX
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())
        
        tr = pd.DataFrame([high_low, high_close, low_close]).max()
        atr = tr.rolling(window=14).mean()
        
        dm_plus = df['high'].diff()
        dm_minus = -df['low'].diff()
        
        dm_plus[dm_plus < 0] = 0
        dm_minus[dm_minus < 0] = 0
        
        di_plus = 100 * (dm_plus.rolling(window=14).mean() / atr)
        di_minus = 100 * (dm_minus.rolling(window=14).mean() / atr)
        
        dx = 100 * abs(di_plus - di_minus) / (di_plus + di_minus)
        adx = dx.rolling(window=14).mean()
        
        return adx.iloc[-1] > 25  # Strong trend if ADX > 25
    except Exception as e:
        logging.error(f"Error calculating trend strength: {e}")
        return False

# Call periodically instead of just in main()
def periodic_performance_check(performance):
    try:
        performance_summary = analyze_trading_performance(performance)
        logging.info(f"Periodic Performance Check: {performance_summary}")
        if performance_summary['win_rate'] < 50:
            logging.warning("Win rate below 50%, consider refining the strategy")
    except Exception as e:
        logging.error(f"Error during periodic performance analysis: {e}")


def main(performance):
    global exchange
    try:
        if not validate_config():
            logging.error("Configuration validation failed")
            return

        # Initialize the exchange only if not already initialized
        if exchange is None:
            exchange = initialize_exchange()
            set_leverage(exchange)
            
        performance = PerformanceMetrics()

        # Health check before trading
        check_exchange_health(exchange)

        # Check trading limits and risk management
        if not performance.can_trade() or not check_risk_limits(performance):
            logging.info("Trading limits reached or risk management restrictions")
            return

        # Check account balance
        balance = exchange.fetch_balance()
        if balance['USDT']['free'] < CONFIG['min_balance']:
            logging.error(f"Insufficient balance: {balance['USDT']['free']} USDT")
            return

        # Fetch and process market data
        ohlcv = fetch_ohlcv(exchange, CONFIG['symbol'], timeframe=CONFIG['timeframe'])
        if ohlcv is None:
            return

        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df = calculate_indicators(df)

        # Re-evaluate risk based on updated conditions
        assess_risk_conditions(df, balance, exchange)

        # Monitor positions and manage risk
        monitor_positions(exchange)

        current_idx = -1
        market_price = df['close'].iloc[current_idx]
        
        # Calculate min order size
        min_order_size = calculate_min_order_size(exchange, CONFIG['symbol'], market_price)
        if min_order_size is None:
            logging.error("Failed to calculate minimum order size")
            return
        
        logging.info(f"Current minimum order size: {min_order_size}")

        # Check funding rate
        side = 'buy' if df['ema_short'].iloc[-1] > df['ema_long'].iloc[-1] else 'sell'
        if not check_funding_rate(exchange, side):
            return

        # Monitor existing positions
        monitor_positions(exchange)

        # Market condition checks
        if not check_market_conditions(df):
            logging.info("Market conditions not favorable for trading")
            return

        # Check market health
        market_health = check_market_health(df)
        if not market_health:
            logging.info("Unfavorable market health conditions")
            return
        
        # Get market data updates
        market_data = update_market_data(df)
        log_market_conditions(df, market_health, market_data)

        # Determine trading action based on signals
        long_condition = (
            df['ema_short'].iloc[current_idx] > df['ema_long'].iloc[current_idx] and
            df['close'].iloc[current_idx] > df['vwap'].iloc[current_idx] and
            df['rsi'].iloc[current_idx] < 45 and
            df['macd'].iloc[current_idx] > df['signal'].iloc[current_idx] and
            df['volume_ratio'].iloc[current_idx] > 1.2 and
            market_health['is_uptrend'] and
            market_health['good_volume'] and
            market_price > market_data['support'] and
            not check_existing_position(exchange, 'buy')
        )

        short_condition = (
            df['ema_short'].iloc[current_idx] < df['ema_long'].iloc[current_idx] and
            df['close'].iloc[current_idx] < df['vwap'].iloc[current_idx] and
            df['rsi'].iloc[current_idx] > 55 and
            df['macd'].iloc[current_idx] < df['signal'].iloc[current_idx] and
            df['volume_ratio'].iloc[current_idx] > 1.2 and
            not market_health['is_uptrend'] and
            market_health['good_volume'] and
            market_price < market_data['resistance'] and
            not check_existing_position(exchange, 'sell')
        )

        if long_condition or short_condition:
            side = 'buy' if long_condition else 'sell'
            trading_decision = "Long" if long_condition else "Short"
            logging.info(f"Evaluating conditions for {trading_decision} entry")

            # Additional checks before order placement
            if not check_trend_strength(df):
                logging.info("Weak trend, skipping trade")
                return
                
            if not analyze_market_depth(exchange, CONFIG['symbol'], side):
                logging.info("Poor market depth, skipping trade")
                return
                
            if not check_signal_quality(df, side, current_idx):
                logging.info("Signal quality check failed")
                return

            # Calculate position parameters
            stop_loss = calculate_dynamic_stop_loss(df, side, market_price)
            take_profit = market_price * (1 + CONFIG['profit_target_percent']) if side == 'buy' else market_price * (1 - CONFIG['profit_target_percent'])

            position_size = calculate_position_size(balance, market_price, stop_loss, exchange)
            position_size = manage_position_risk(position_size, market_price, balance)

            # Validate position size
            if not validate_position_size(position_size, market_price, balance, min_order_size):
                return

            # Validate order size
            if not validate_order_size(position_size, market_price, balance):
                logging.info("Invalid order size, skipping trade")
                return

            position_size = limit_position_size(position_size, market_price, balance)

            # Place order
            order = place_order_with_sl_tp(
                exchange=exchange,
                side=side,
                amount=position_size,
                market_price=market_price,
                stop_loss_price=stop_loss,
                take_profit_price=take_profit
            )

            if order:
                trade_result = {
                    'timestamp': datetime.now().isoformat(),
                    'profit': 0,  # Initial trade entry
                    'side': side,
                    'entry_price': market_price,
                    'position_size': position_size,
                    'fees': position_size * market_price * CONFIG['fee_rate']
                }
                performance.update_trade(0)  # Trade initially added
                update_performance_metrics(performance, trade_result)
                logging.info(f"{side.title()} order successfully placed with position size: {position_size}")
            else:
                logging.error("Failed to place order")
    except ccxt.NetworkError as e:
        logging.error(f"Network error during exchange initialization: {str(e)}")
        return
    except ccxt.ExchangeError as e:
        logging.error(f"Exchange error during exchange initialization: {str(e)}")
        return
    except Exception as e:
        logging.error(f"Unexpected error during exchange initialization: {str(e)}")
        return
    except Exception as e:
        logging.error(f'Critical error in main loop: {str(e)}')
        raise


if __name__ == '__main__':
    consecutive_errors = 0
    last_performance_analysis = datetime.now()
    performance = PerformanceMetrics()

    while True:
        try:
            # System health check
            if not check_system_health():
                logging.warning("System health check failed, waiting...")
                time.sleep(300)
                continue
                
            # Analyze performance periodically (every 4 hours)
            if (datetime.now() - last_performance_analysis).total_seconds() > 14400:
                analyze_trading_performance(performance)
                last_performance_analysis = datetime.now()
            
            # Cleanup and main execution
            if 'exchange' in locals():
                cleanup_old_orders(exchange)
            
            main(performance)
            consecutive_errors = 0
            time.sleep(60)
            
        except ccxt.NetworkError as e:
            if recover_from_error(exchange, e):
                consecutive_errors += 1
                continue
            else:
                if 'exchange' in locals():
                    emergency_stop(exchange)
                raise
                
        except KeyboardInterrupt:
            logging.info("Bot stopped by user")
            if 'exchange' in locals():
                emergency_stop(exchange)
            break
                
        except Exception as e:
            consecutive_errors += 1
            if not recover_from_error(exchange, e):
                logging.error(f'Unrecoverable error: {e}')
                if consecutive_errors > 5:
                    logging.critical("Too many consecutive errors, stopping bot")
                    if 'exchange' in locals():
                        emergency_stop(exchange)
                    break
            
            sleep_time = min(60 * (2 ** consecutive_errors), 3600)
            logging.warning(f'Sleeping for {sleep_time} seconds before retry')
            time.sleep(sleep_time)