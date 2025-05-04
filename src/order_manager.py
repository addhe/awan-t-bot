import logging
import ccxt
from typing import Dict, Any

from config import CONFIG


def place_order_with_sl_tp(
    exchange: ccxt.Exchange,
    side: str,
    amount: float,
    price: float,
    stop_loss: float,
    take_profit: float,
) -> Dict[str, Any]:
    """
    Place a main order with stop loss and take profit orders.

    Args:
        exchange: The exchange instance
        side: 'buy' or 'sell'
        amount: Position size
        price: Entry price
        stop_loss: Stop loss price
        take_profit: Take profit price

    Returns:
        Dict containing order status and IDs
    """
    try:
        # Place main order
        main_order = exchange.create_order(
            symbol=CONFIG["symbol"],
            type="LIMIT",
            side=side,
            amount=amount,
            price=price,
        )

        # Wait for main order to fill
        filled_order = exchange.fetch_order(main_order["id"], CONFIG["symbol"])
        if filled_order["status"] != "closed":
            logging.warning("Main order not filled immediately")
            return {"success": False, "message": "Main order not filled"}

        # Calculate opposite side for SL/TP
        opposite_side = "sell" if side == "buy" else "buy"

        # Place stop loss
        sl_order = exchange.create_order(
            symbol=CONFIG["symbol"],
            type="STOP_MARKET",
            side=opposite_side,
            amount=amount,
            params={"stopPrice": stop_loss, "reduceOnly": True},
        )

        # Place take profit (split into two parts)
        tp1_amount = amount * CONFIG["partial_tp_1"]
        tp2_amount = amount * CONFIG["partial_tp_2"]
        tp1_price = (
            price * (1 + CONFIG["tp1_target"])
            if side == "buy"
            else price * (1 - CONFIG["tp1_target"])
        )
        tp2_price = (
            price * (1 + CONFIG["tp2_target"])
            if side == "buy"
            else price * (1 - CONFIG["tp2_target"])
        )

        tp1_order = exchange.create_order(
            symbol=CONFIG["symbol"],
            type="LIMIT",
            side=opposite_side,
            amount=tp1_amount,
            price=tp1_price,
            params={"reduceOnly": True},
        )

        tp2_order = exchange.create_order(
            symbol=CONFIG["symbol"],
            type="LIMIT",
            side=opposite_side,
            amount=tp2_amount,
            price=tp2_price,
            params={"reduceOnly": True},
        )

        logging.info(
            "Orders placed - Main: %s, SL: %s, TP1: %s, TP2: %s",
            main_order['id'], sl_order['id'], tp1_order['id'], tp2_order['id']
        )

        return {
            "success": True,
            "orders": {
                "main": main_order["id"],
                "sl": sl_order["id"],
                "tp1": tp1_order["id"],
                "tp2": tp2_order["id"],
            },
        }

    except Exception as e:
        logging.error(
            f"Error placing orders: {e}"
        )
        return {"success": False, "message": str(e)}


def set_leverage(exchange: ccxt.Exchange) -> bool:
    """
    Set leverage for trading.

    Args:
        exchange: The exchange instance

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        exchange.fapiPrivatePostLeverage(
            {
                "symbol": exchange.market(CONFIG["symbol"])["id"],
                "leverage": CONFIG["leverage"],
            }
        )
        logging.info(
            f"Leverage set to {CONFIG['leverage']}x"
        )
        return True

    except Exception as e:
        logging.error(
            f"Failed to set leverage: {e}"
        )
        return False


def check_funding_rate(exchange: ccxt.Exchange) -> Dict[str, Any]:
    """
    Check funding rate and determine if it's favorable for trading.

    Args:
        exchange: The exchange instance

    Returns:
        Dict containing funding rate info and whether to wait
    """
    try:
        funding_rate = exchange.fetch_funding_rate(CONFIG["symbol"])
        current_rate = float(funding_rate["fundingRate"])

        # If funding rate is too high (unfavorable), wait
        should_wait = abs(current_rate) > CONFIG["funding_rate_threshold"]

        return {
            "success": True,
            "funding_rate": current_rate,
            "should_wait": should_wait,
            "next_funding_time": funding_rate["nextFundingTime"],
        }

    except Exception as e:
        logging.error(
            f"Error checking funding rate: {e}"
        )
        return {"success": False, "should_wait": True, "error": str(e)}


def close_position(
    exchange: ccxt.Exchange, symbol: str, position_side: str
) -> bool:
    """
    Close an open position.

    Args:
        exchange: The exchange instance
        symbol: Trading pair symbol
        position_side: 'long' or 'short'

    Returns:
        bool: True if position closed successfully
    """
    try:
        positions = exchange.fetch_positions([symbol])
        for position in positions:
            if (
                position["side"] == position_side
                and float(position["contracts"]) > 0
            ):
                side = "sell" if position_side == "long" else "buy"
                exchange.create_order(
                    symbol=symbol,
                    type="MARKET",
                    side=side,
                    amount=float(position["contracts"]),
                    params={"reduceOnly": True},
                )
                logging.info(
                    f"Closed {position_side} position for {symbol}"
                )
                return True

        return False

    except Exception as e:
        logging.error(
            f"Error closing position: {e}"
        )
        return False


def cleanup_old_orders(exchange: ccxt.Exchange) -> None:
    """
    Cancel old pending orders.

    Args:
        exchange: The exchange instance
    """
    try:
        open_orders = exchange.fetch_open_orders(CONFIG["symbol"])
        for order in open_orders:
            if order["status"] == "open":
                exchange.cancel_order(order["id"], CONFIG["symbol"])
                logging.info(
                    f"Cancelled old order {order['id']}"
                )

    except Exception as e:
        logging.error(
            f"Error cleaning up orders: {e}"
        )
