-- Initialize PostgreSQL database for trading bot

-- Create extension for TimescaleDB
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Create OHLCV table
CREATE TABLE IF NOT EXISTS ohlcv (
    timestamp TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    open NUMERIC NOT NULL,
    high NUMERIC NOT NULL,
    low NUMERIC NOT NULL,
    close NUMERIC NOT NULL,
    volume NUMERIC NOT NULL,
    PRIMARY KEY (timestamp, symbol, timeframe)
);

-- Convert to hypertable
SELECT create_hypertable('ohlcv', 'timestamp', if_not_exists => TRUE);

-- Create indicators table
CREATE TABLE IF NOT EXISTS indicators (
    timestamp TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    indicator_name TEXT NOT NULL,
    value NUMERIC NOT NULL,
    PRIMARY KEY (timestamp, symbol, timeframe, indicator_name)
);

-- Convert to hypertable
SELECT create_hypertable('indicators', 'timestamp', if_not_exists => TRUE);

-- Create trades table
CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    entry_time TIMESTAMPTZ NOT NULL,
    exit_time TIMESTAMPTZ,
    entry_price NUMERIC NOT NULL,
    exit_price NUMERIC,
    quantity NUMERIC NOT NULL,
    profit_pct NUMERIC,
    close_reason TEXT,
    buy_order_id TEXT,
    sell_order_id TEXT
);

-- Create index on symbol for faster queries
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);

-- Create signals table
CREATE TABLE IF NOT EXISTS signals (
    timestamp TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    signal TEXT NOT NULL,
    confidence NUMERIC NOT NULL,
    PRIMARY KEY (timestamp, symbol, timeframe)
);

-- Convert to hypertable
SELECT create_hypertable('signals', 'timestamp', if_not_exists => TRUE);

-- Create retention policy (keep data for 1 year)
SELECT add_retention_policy('ohlcv', INTERVAL '1 year', if_not_exists => TRUE);
SELECT add_retention_policy('indicators', INTERVAL '1 year', if_not_exists => TRUE);
SELECT add_retention_policy('signals', INTERVAL '1 year', if_not_exists => TRUE);
