-- V6.1 SimEdge 数据库迁移脚本
-- 创建模拟盘相关数据表
-- 执行方式: sqlite3 data/simulation.db < migrations/v6.1_simulation_schema.sql

-- 模拟账户表
CREATE TABLE IF NOT EXISTS sim_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_name TEXT NOT NULL,
    initial_capital REAL NOT NULL,
    available_cash REAL NOT NULL,
    total_value REAL NOT NULL,
    total_profit REAL DEFAULT 0,
    total_return_pct REAL DEFAULT 0,
    max_drawdown REAL DEFAULT 0,
    sharpe_ratio REAL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'active'
);

-- 模拟持仓表
CREATE TABLE IF NOT EXISTS sim_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    stock_code TEXT NOT NULL,
    stock_name TEXT,
    quantity INTEGER NOT NULL,
    avg_cost REAL NOT NULL,
    current_price REAL,
    market_value REAL,
    unrealized_pnl REAL,
    unrealized_pnl_pct REAL,
    sector TEXT,
    opened_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(account_id, stock_code)
);

-- 模拟订单表
CREATE TABLE IF NOT EXISTS sim_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    order_id TEXT UNIQUE NOT NULL,
    stock_code TEXT NOT NULL,
    order_type TEXT NOT NULL,  -- MARKET, LIMIT
    action TEXT NOT NULL,       -- BUY, SELL
    quantity INTEGER NOT NULL,
    price REAL,
    filled_quantity INTEGER DEFAULT 0,
    filled_price REAL,
    status TEXT DEFAULT 'pending',  -- pending, partial, filled, cancelled, rejected
    strategy TEXT,
    signal_id INTEGER,
    commission REAL DEFAULT 0,
    slippage REAL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    filled_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 模拟成交表
CREATE TABLE IF NOT EXISTS sim_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    order_id TEXT NOT NULL,
    transaction_id TEXT UNIQUE NOT NULL,
    stock_code TEXT NOT NULL,
    action TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    price REAL NOT NULL,
    amount REAL NOT NULL,
    commission REAL NOT NULL,
    stamp_tax REAL DEFAULT 0,
    transfer_fee REAL DEFAULT 0,
    total_cost REAL NOT NULL,
    realized_pnl REAL,
    transaction_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 资金流水表
CREATE TABLE IF NOT EXISTS sim_fund_flow (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    flow_type TEXT NOT NULL,  -- initial_capital, buy_order, sell_order, commission, tax
    amount REAL NOT NULL,
    balance_after REAL NOT NULL,
    reference_id TEXT,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 权益曲线表
CREATE TABLE IF NOT EXISTS sim_equity_curve (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_value REAL NOT NULL,
    cash REAL NOT NULL,
    positions_value REAL NOT NULL,
    unrealized_pnl REAL,
    benchmark_value REAL
);

-- 创建索引以优化查询性能
CREATE INDEX IF NOT EXISTS idx_orders_account ON sim_orders(account_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON sim_orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_stock ON sim_orders(stock_code);
CREATE INDEX IF NOT EXISTS idx_positions_account ON sim_positions(account_id);
CREATE INDEX IF NOT EXISTS idx_positions_stock ON sim_positions(stock_code);
CREATE INDEX IF NOT EXISTS idx_transactions_account ON sim_transactions(account_id);
CREATE INDEX IF NOT EXISTS idx_transactions_order ON sim_transactions(order_id);
CREATE INDEX IF NOT EXISTS idx_fundflow_account ON sim_fund_flow(account_id);
CREATE INDEX IF NOT EXISTS idx_fundflow_type ON sim_fund_flow(flow_type);
CREATE INDEX IF NOT EXISTS idx_equity_account ON sim_equity_curve(account_id);
CREATE INDEX IF NOT EXISTS idx_equity_time ON sim_equity_curve(timestamp);

-- 插入默认模拟账户（如果需要）
INSERT OR IGNORE INTO sim_accounts (account_name, initial_capital, available_cash, total_value, status)
VALUES ('默认模拟账户', 1000000, 1000000, 1000000, 'active');

-- 迁移完成提示
SELECT 'V6.1 SimEdge 数据库迁移完成' AS message;
SELECT '已创建以下表:' AS message;
SELECT '- sim_accounts (模拟账户表)' AS tables;
SELECT '- sim_positions (模拟持仓表)' AS tables;
SELECT '- sim_orders (模拟订单表)' AS tables;
SELECT '- sim_transactions (模拟成交表)' AS tables;
SELECT '- sim_fund_flow (资金流水表)' AS tables;
SELECT '- sim_equity_curve (权益曲线表)' AS tables;
