from flask import Flask, render_template, request, jsonify
import os
import sys
import json
import threading
import time
from quant_engine.config_loader import ConfigLoader
from quant_engine.okx_client import OKXClient

# Add current directory to sys.path to allow importing strategies
sys.path.append(os.getcwd())

app = Flask(__name__, 
            template_folder=os.path.join(os.getcwd(), 'templates'),
            static_folder=os.path.join(os.getcwd(), 'static'))
app.secret_key = 'okx_quant_secret_key'

# Print registered routes
print("Registered Routes:")
print(app.url_map)

@app.route('/ping')
def ping():
    return "pong"

# Initialize Config
CONFIG_PATH = os.path.join(os.getcwd(), '配置.txt')
config_loader = ConfigLoader(CONFIG_PATH)

import requests
from quant_engine.strategy_framework import *
from datetime import datetime

@app.route('/')
def home():
    try:
        return render_template('index.html')
    except Exception as e:
        return str(e), 500

@app.route('/api/config', methods=['GET', 'POST'])
def handle_config():
    if request.method == 'POST':
        data = request.json
        config_loader.save_config(data)
        return jsonify({'status': 'success', 'msg': '配置已保存'})
    else:
        return jsonify(config_loader.config)

@app.route('/api/reset_database', methods=['POST'])
def reset_database():
    """Reset database - clear all data while preserving table structure"""
    from quant_engine.db import reset_database as db_reset
    result = db_reset()
    if result['status'] == 'success':
        deleted = result['deleted']
        total = sum(deleted.values())
        msg = f"数据库已初始化，共清除 {total} 条记录"
        return jsonify({'status': 'success', 'msg': msg, 'details': deleted})
    else:
        return jsonify({'status': 'error', 'msg': result.get('msg', '初始化失败')})

@app.route('/api/account')
def get_account_info():
    client = get_okx_client()
    if not client:
        return jsonify({'status': 'error', 'msg': '请先配置API Key'})
    
    balance = client.get_account_balance()
    positions = client.get_positions()
    
    if balance.get('code') != '0':
        return jsonify({'status': 'error', 'msg': f"获取余额失败: {balance.get('msg')}"})
        
    # Fix for missing account-level availEq
    if balance.get('data') and len(balance['data']) > 0:
        data = balance['data'][0]
        if not data.get('availEq'):
            # Try to find USDT balance
            for detail in data.get('details', []):
                if detail.get('ccy') == 'USDT':
                    data['availEq'] = detail.get('availEq')
                    break
    
    if positions.get('code') != '0':
        return jsonify({'status': 'error', 'msg': f"获取持仓失败: {positions.get('msg')}"})
    
    return jsonify({
        'status': 'success',
        'balance': balance,
        'positions': positions
    })

@app.route('/api/strategies')
def list_strategies():
    strategy_dir = os.path.join(os.getcwd(), 'strategy')
    strategies = []
    
    from quant_engine.db import get_all_strategies_status, get_strategy_metrics
    db_status = get_all_strategies_status()
    
    if os.path.exists(strategy_dir):
        for f in os.listdir(strategy_dir):
            if f.endswith('.py'):
                status_info = db_status.get(f, {})
                metrics = get_strategy_metrics(f)
                
                strategies.append({
                    'name': f,
                    'status': status_info.get('status', 'STOPPED'),
                    'symbol': status_info.get('symbol', '-'),
                    'last_heartbeat': status_info.get('last_heartbeat', '-'),
                    'total_pnl': metrics.get('total_pnl', 0),
                    'total_trades': metrics.get('total_trades', 0)
                })
    return jsonify({'strategies': strategies})

# AI Generation
@app.route('/api/ai_generate', methods=['POST'])
def ai_generate():
    data = request.json
    prompt = data.get('prompt')
    
    api_key = config_loader.get('OPENAI_API_KEY')
    base_url = config_loader.get('OPENAI_API_BASE_URL')
    model = config_loader.get('OPENAI_MODEL')
    
    if not api_key:
        return jsonify({'status': 'error', 'msg': '请先配置AI API Key'})
        
    system_prompt = """
You are a professional quantitative strategy developer for OKX cryptocurrency exchange.
Generate Python strategy code based on user requirements.

IMPORTANT: Use ONLY English for all variable names, comments, and strings to avoid encoding issues.

The code MUST follow this exact framework structure:

```
class Strategy(StrategyBase):
    def initialize(self):
        declare_strategy_type(AlgoStrategyType.SECURITY)
        self.trigger_symbols()
        self.global_variables()

    def trigger_symbols(self):
        self.symbol = declare_trig_symbol()

    def global_variables(self):
        # Define all strategy variables here using show_variable()
        # Example: self.threshold = show_variable(0.02, GlobalType.FLOAT)
        pass

    def handle_data(self):
        try:
            self.execute_strategy()
        except Exception as e:
            print(f"Strategy error: {e}")

    def execute_strategy(self):
        # Main trading logic here
        pass
```

AVAILABLE FUNCTIONS:
1. declare_strategy_type(AlgoStrategyType.SECURITY) - Required in initialize()
2. declare_trig_symbol() - Returns the trading symbol (e.g., "BTC-USDT")
3. show_variable(value, GlobalType.FLOAT/INT) - Define persistent variables
4. current_price(symbol=self.symbol, price_type=THType.FTH) - Get current price
5. max_qty_to_sell(symbol=self.symbol) - Get position quantity available to sell
6. max_qty_to_buy_on_cash(symbol=self.symbol, order_type=OrdType.LMT, price=crt_price) - Get max buyable qty with cash (returns USDT amount / price)
7. position_pl_ratio(symbol=self.symbol, cost_price_model=CostPriceModel.AVG) - Get position P&L ratio
8. place_limit(symbol=self.symbol, price=price, qty=qty, side=OrderSide.BUY/SELL, time_in_force=TimeInForce.GTC) - Place limit order

AVAILABLE ENUMS:
- AlgoStrategyType.SECURITY
- GlobalType.FLOAT, GlobalType.INT
- THType.FTH
- OrderSide.BUY, OrderSide.SELL
- TimeInForce.GTC, TimeInForce.DAY
- OrdType.LMT, OrdType.MKT
- CostPriceModel.AVG

STRATEGY GUIDELINES:
1. Use self.symbol for all symbol parameters
2. Calculate available_usdt = max_buy_qty * crt_price for available funds
3. Use base_order_usdt (e.g., 100.0) as minimum order amount in USDT
4. For buy: buy_qty = buy_usdt / crt_price
5. For sell: use position_qty from max_qty_to_sell()
6. Always add initialization flag to avoid repeated init actions
7. Track recent_high and recent_low for price movement analysis
8. Include take-profit and stop-loss logic when appropriate
9. Print status messages for debugging (use English)
10. Handle edge cases: price <= 0, position_qty <= 0, available_usdt < minimum

EXAMPLE PATTERN for execute_strategy():
```
def execute_strategy(self):
    crt_price = current_price(symbol=self.symbol, price_type=THType.FTH)
    if crt_price <= 0:
        return

    position_qty = max_qty_to_sell(symbol=self.symbol)
    max_buy_qty = max_qty_to_buy_on_cash(symbol=self.symbol, order_type=OrdType.LMT, price=crt_price)
    available_usdt = max_buy_qty * crt_price

    print(f"Price: {crt_price:.2f}, Position: {position_qty:.6f}, Available: {available_usdt:.2f} USDT")

    # Your trading logic here...
    # Example buy:
    # if condition_met and available_usdt >= self.base_order_usdt:
    #     buy_qty = self.base_order_usdt / crt_price
    #     place_limit(symbol=self.symbol, price=crt_price, qty=buy_qty, side=OrderSide.BUY, time_in_force=TimeInForce.GTC)

    # Example sell:
    # if sell_condition and position_qty > 0:
    #     sell_qty = position_qty * 0.5
    #     place_limit(symbol=self.symbol, price=crt_price, qty=sell_qty, side=OrderSide.SELL, time_in_force=TimeInForce.GTC)
```

Return ONLY the Python code without any markdown formatting or explanation.
Do NOT use Chinese characters anywhere in the code.
    """
    
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
        }
        
        response = requests.post(f"{base_url}/v1/chat/completions", headers=headers, json=payload)
        result = response.json()
        
        if 'choices' in result and len(result['choices']) > 0:
            code = result['choices'][0]['message']['content']
            # Clean up code if it has markdown blocks
            code = code.strip()
            # Remove markdown code blocks
            if '```python' in code:
                start = code.find('```python') + 9
                end = code.rfind('```')
                if end > start:
                    code = code[start:end].strip()
            elif '```' in code:
                start = code.find('```') + 3
                end = code.rfind('```')
                if end > start:
                    code = code[start:end].strip()

            # Validate the code has required structure
            if 'class Strategy' not in code:
                return jsonify({'status': 'error', 'msg': 'Generated code missing Strategy class'})
            if 'def handle_data' not in code:
                return jsonify({'status': 'error', 'msg': 'Generated code missing handle_data method'})

            return jsonify({'status': 'success', 'code': code})
        else:
            return jsonify({'status': 'error', 'msg': 'AI未返回有效结果: ' + str(result)})
            
    except Exception as e:
        return jsonify({'status': 'error', 'msg': str(e)})

@app.route('/api/save_strategy', methods=['POST'])
def save_strategy():
    data = request.json
    name = data.get('name')
    code = data.get('code')

    if not name.endswith('.py'):
        name += '.py'

    path = os.path.join(os.getcwd(), 'strategy', name)
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(code)
        return jsonify({'status': 'success', 'msg': '策略已保存'})
    except Exception as e:
        return jsonify({'status': 'error', 'msg': str(e)})

@app.route('/api/get_strategy_code/<strategy_name>')
def get_strategy_code(strategy_name):
    """Get the source code of a strategy"""
    path = os.path.join(os.getcwd(), 'strategy', strategy_name)
    if not os.path.exists(path):
        return jsonify({'status': 'error', 'msg': '策略文件不存在'})

    try:
        with open(path, 'r', encoding='utf-8') as f:
            code = f.read()
        return jsonify({'status': 'success', 'code': code})
    except Exception as e:
        return jsonify({'status': 'error', 'msg': str(e)})

@app.route('/api/update_strategy', methods=['POST'])
def update_strategy():
    """Update an existing strategy's code"""
    data = request.json
    name = data.get('name')
    code = data.get('code')

    if not name:
        return jsonify({'status': 'error', 'msg': '策略名称不能为空'})

    path = os.path.join(os.getcwd(), 'strategy', name)
    if not os.path.exists(path):
        return jsonify({'status': 'error', 'msg': '策略文件不存在'})

    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(code)
        return jsonify({'status': 'success', 'msg': f'策略 {name} 已更新'})
    except Exception as e:
        return jsonify({'status': 'error', 'msg': str(e)})

@app.route('/api/delete_strategy', methods=['POST'])
def delete_strategy():
    """Delete a strategy file and its database records"""
    data = request.json
    name = data.get('name')

    if not name:
        return jsonify({'status': 'error', 'msg': '策略名称不能为空'})

    # Check if strategy is running
    from quant_engine.db import get_all_strategies_status
    db_status = get_all_strategies_status()
    status_info = db_status.get(name, {})

    if status_info.get('status') == 'RUNNING':
        return jsonify({'status': 'error', 'msg': '无法删除正在运行的策略，请先停止策略'})

    path = os.path.join(os.getcwd(), 'strategy', name)
    if not os.path.exists(path):
        return jsonify({'status': 'error', 'msg': '策略文件不存在'})

    try:
        # Delete the file
        os.remove(path)

        # Delete database records
        from quant_engine.db import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM strategy_status WHERE name = ?', (name,))
        cursor.execute('DELETE FROM strategy_logs WHERE strategy_name = ?', (name,))
        cursor.execute('DELETE FROM strategy_trades WHERE strategy_name = ?', (name,))
        cursor.execute('DELETE FROM strategy_metrics WHERE strategy_name = ?', (name,))
        conn.commit()
        conn.close()

        return jsonify({'status': 'success', 'msg': f'策略 {name} 已删除'})
    except Exception as e:
        return jsonify({'status': 'error', 'msg': str(e)})

# Strategy Runner
active_strategies = {}

def run_strategy_thread(strategy_name, symbol, leverage, client, interval_bar='1H'):
    """
    Run strategy in a separate thread with actual trading

    Args:
        strategy_name: Name of strategy file
        symbol: Trading pair (e.g., BTC-USDT)
        leverage: Leverage multiplier
        client: OKX client instance
        interval_bar: K-line interval (1m, 5m, 15m, 1H, 4H, 1D)
    """
    path = os.path.join(os.getcwd(), 'strategy', strategy_name)

    # Map bar to sleep interval in seconds
    bar_intervals = {
        '1m': 60,
        '5m': 300,
        '15m': 900,
        '1H': 3600,
        '4H': 14400,
        '1D': 86400
    }
    sleep_interval = bar_intervals.get(interval_bar, 3600)

    # Prepare execution scope
    scope = globals().copy()
    scope.update({
        'StrategyBase': StrategyBase,
        'AlgoStrategyType': AlgoStrategyType,
        'GlobalType': GlobalType,
        'THType': THType,
        'OrderSide': OrderSide,
        'TimeInForce': TimeInForce,
        'OrdType': OrdType,
        'CostPriceModel': CostPriceModel,
        'declare_strategy_type': declare_strategy_type,
        'declare_trig_symbol': lambda: symbol,
        'show_variable': show_variable,
        'current_price': current_price,
        'max_qty_to_sell': max_qty_to_sell,
        'max_qty_to_buy_on_cash': max_qty_to_buy_on_cash,
        'max_qty_to_buy_on_margin': max_qty_to_buy_on_margin,
        'position_pl_ratio': position_pl_ratio,
        'place_limit': place_limit,
        'ceil': ceil
    })

    try:
        with open(path, 'r', encoding='utf-8') as f:
            code = f.read()

        exec(code, scope)

        if 'Strategy' in scope:
            # Set context for global functions - CRITICAL for real trading
            set_context(client, symbol, strategy_name)

            strategy_instance = scope['Strategy'](client, symbol, strategy_name)
            strategy_instance.loop_interval = sleep_interval
            active_strategies[strategy_name] = {
                'instance': strategy_instance,
                'thread': threading.current_thread(),
                'symbol': symbol,
                'interval': interval_bar
            }

            print(f"[LIVE] Starting strategy {strategy_name} on {symbol}, interval: {interval_bar} ({sleep_interval}s)")

            from quant_engine.db import log_strategy_event, update_strategy_status
            log_strategy_event(strategy_name, 'INFO', 'START',
                f'Strategy started: symbol={symbol}, interval={interval_bar}, leverage={leverage}')
            update_strategy_status(strategy_name, 'RUNNING')

            # Run strategy with custom interval
            strategy_instance.initialize()
            strategy_instance.is_running = True

            while strategy_instance.is_running:
                try:
                    # Check if strategy should stop
                    from quant_engine.db import get_db_connection
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute('SELECT status FROM strategy_status WHERE name = ?', (strategy_name,))
                    row = cursor.fetchone()
                    conn.close()

                    if row and row[0] == 'STOPPED':
                        print(f"[LIVE] Strategy {strategy_name} stopped by user")
                        break

                    # Execute strategy logic
                    strategy_instance.handle_data()

                    # Update heartbeat
                    update_strategy_status(strategy_name, 'RUNNING')

                except Exception as e:
                    error_msg = f"Error in strategy loop: {e}"
                    print(f"[LIVE] {error_msg}")
                    log_strategy_event(strategy_name, 'ERROR', 'ERROR', error_msg)

                time.sleep(sleep_interval)

            log_strategy_event(strategy_name, 'INFO', 'STOP', 'Strategy stopped')
            update_strategy_status(strategy_name, 'STOPPED')

        else:
            print(f"No Strategy class found in {strategy_name}")

    except Exception as e:
        error_msg = f"Error running strategy {strategy_name}: {e}"
        print(f"[LIVE] {error_msg}")
        from quant_engine.db import log_strategy_event, update_strategy_status
        log_strategy_event(strategy_name, 'ERROR', 'ERROR', error_msg)
        update_strategy_status(strategy_name, 'ERROR', error_msg)
    finally:
        if strategy_name in active_strategies:
            del active_strategies[strategy_name]

# Initialize OKX Client
def get_okx_client():
    api_key = config_loader.get('OKX_API_KEY')
    secret_key = config_loader.get('OKX_SECRET_KEY')
    passphrase = config_loader.get('OKX_PASSPHRASE')
    base_url = config_loader.get('OKX_API_ENDPOINT', 'https://www.okx.com')
    proxy_url = config_loader.get('PROXY_URL')
    if api_key and secret_key and passphrase:
        return OKXClient(api_key, secret_key, passphrase, base_url, proxy_url)
    return None

@app.route('/api/run_strategy', methods=['POST'])
def run_strategy():
    """
    Mark strategy as RUNNING in database.
    The scheduler.py will pick it up and start the actual process.
    """
    data = request.json
    strategy_name = data.get('strategy_name')
    symbol = data.get('symbol', 'BTC-USDT')
    leverage = data.get('leverage', 1)
    interval_bar = data.get('interval', '1H')  # K-line interval

    # Validate API Key configuration
    client = get_okx_client()
    if not client:
        return jsonify({'status': 'error', 'msg': '请先配置API Key'})

    # Validate interval
    valid_intervals = ['1m', '5m', '15m', '1H', '4H', '1D']
    if interval_bar not in valid_intervals:
        interval_bar = '1H'

    # Update database - scheduler.py will pick this up and start the process
    from quant_engine.db import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO strategy_status (name, symbol, leverage, interval, status, last_heartbeat)
        VALUES (?, ?, ?, ?, 'RUNNING', datetime('now'))
    ''', (strategy_name, symbol, leverage, interval_bar))
    conn.commit()
    conn.close()

    # Map interval to description
    interval_desc = {
        '1m': '1分钟', '5m': '5分钟', '15m': '15分钟',
        '1H': '1小时', '4H': '4小时', '1D': '1天'
    }

    return jsonify({
        'status': 'success',
        'msg': f'策略 {strategy_name} 已提交启动，交易对: {symbol}，周期: {interval_desc.get(interval_bar, interval_bar)}，请确保 scheduler.py 正在运行'
    })

@app.route('/api/stop_strategy', methods=['POST'])
def stop_strategy():
    data = request.json
    strategy_name = data.get('strategy_name')

    from quant_engine.db import update_strategy_status, log_strategy_event

    # Stop the strategy instance if running
    if strategy_name in active_strategies:
        strategy_info = active_strategies[strategy_name]
        if 'instance' in strategy_info:
            strategy_info['instance'].is_running = False
        log_strategy_event(strategy_name, 'INFO', 'STOP', 'Strategy stop requested by user')

    update_strategy_status(strategy_name, 'STOPPED')

    return jsonify({'status': 'success', 'msg': f'策略 {strategy_name} 已停止'})

# Strategy Monitoring APIs
@app.route('/api/strategy_logs/<strategy_name>')
def get_strategy_logs_api(strategy_name):
    """Get logs for a specific strategy"""
    from quant_engine.db import get_strategy_logs
    
    limit = request.args.get('limit', 100, type=int)
    level = request.args.get('level', None)
    
    logs = get_strategy_logs(strategy_name, limit=limit, level=level)
    
    # Convert datetime to string for JSON serialization
    for log in logs:
        if log.get('timestamp'):
            log['timestamp'] = str(log['timestamp'])
    
    return jsonify({'status': 'success', 'logs': logs})

@app.route('/api/strategy_trades/<strategy_name>')
def get_strategy_trades_api(strategy_name):
    """Get trade history for a specific strategy"""
    from quant_engine.db import get_strategy_trades
    
    limit = request.args.get('limit', 50, type=int)
    trades = get_strategy_trades(strategy_name, limit=limit)
    
    # Convert datetime to string for JSON serialization
    for trade in trades:
        if trade.get('timestamp'):
            trade['timestamp'] = str(trade['timestamp'])
    
    return jsonify({'status': 'success', 'trades': trades})

@app.route('/api/strategy_metrics/<strategy_name>')
def get_strategy_metrics_api(strategy_name):
    """Get performance metrics for a specific strategy"""
    from quant_engine.db import get_strategy_metrics
    
    metrics = get_strategy_metrics(strategy_name)
    
    # Convert datetime to string for JSON serialization
    if metrics.get('last_updated'):
        metrics['last_updated'] = str(metrics['last_updated'])
    
    return jsonify({'status': 'success', 'metrics': metrics})

@app.route('/api/strategy_status/<strategy_name>')
def get_strategy_status_api(strategy_name):
    """Get complete status for a strategy including logs, trades, and metrics"""
    from quant_engine.db import (
        get_all_strategies_status,
        get_strategy_logs,
        get_strategy_trades,
        get_strategy_metrics
    )
    
    db_status = get_all_strategies_status()
    status_info = db_status.get(strategy_name, {})
    
    logs = get_strategy_logs(strategy_name, limit=20)
    trades = get_strategy_trades(strategy_name, limit=10)
    metrics = get_strategy_metrics(strategy_name)
    
    # Convert datetime to string for JSON serialization
    for log in logs:
        if log.get('timestamp'):
            log['timestamp'] = str(log['timestamp'])
    
    for trade in trades:
        if trade.get('timestamp'):
            trade['timestamp'] = str(trade['timestamp'])
    
    if metrics.get('last_updated'):
        metrics['last_updated'] = str(metrics['last_updated'])
    
    if status_info.get('last_heartbeat'):
        status_info['last_heartbeat'] = str(status_info['last_heartbeat'])
    
    return jsonify({
        'status': 'success',
        'strategy_info': status_info,
        'logs': logs,
        'trades': trades,
        'metrics': metrics
    })


@app.route('/api/backtest', methods=['POST'])
def run_backtest():
    data = request.json
    strategy_name = data.get('strategy_name')
    symbol = data.get('symbol', 'BTC-USDT')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    mode = data.get('mode', 'database')  # 'database' 或 'live'
    bar = data.get('bar', '1H')
    initial_balance = data.get('initial_balance', 10000.0)

    path = os.path.join(os.getcwd(), 'strategy', strategy_name)
    if not os.path.exists(path):
        return jsonify({'status': 'error', 'msg': '策略文件不存在'})

    with open(path, 'r', encoding='utf-8') as f:
        code = f.read()

    from quant_engine.backtest_engine import BacktestEngine, BacktestMode
    backtest_mode = BacktestMode.DATABASE if mode == 'database' else BacktestMode.LIVE
    engine = BacktestEngine(code, symbol, start_date, end_date, mode=backtest_mode, bar=bar, initial_balance=initial_balance)
    result = engine.run()

    return jsonify(result)


# ========== 市场数据管理API ==========

@app.route('/api/market_data/sync', methods=['POST'])
def sync_market_data():
    """同步历史K线数据到数据库"""
    data = request.json
    symbol = data.get('symbol', 'BTC-USDT')
    bar = data.get('bar', '1H')
    start_date = data.get('start_date', '2024-01-01')
    end_date = data.get('end_date')

    from quant_engine.market_data import MarketDataManager

    client = get_okx_client()
    manager = MarketDataManager(client)

    result = manager.fetch_and_save_klines(symbol, bar, start_date, end_date)

    return jsonify(result)


@app.route('/api/market_data/info')
def get_market_data_info():
    """获取已存储的市场数据信息"""
    symbol = request.args.get('symbol')
    bar = request.args.get('bar')

    from quant_engine.market_data import MarketDataManager

    manager = MarketDataManager()
    info = manager.get_data_info(symbol, bar)

    return jsonify({'status': 'success', 'data': info})


@app.route('/api/market_data/delete', methods=['POST'])
def delete_market_data():
    """删除指定的市场数据"""
    data = request.json
    symbol = data.get('symbol')
    bar = data.get('bar')

    if not symbol:
        return jsonify({'status': 'error', 'msg': '请指定交易对'})

    from quant_engine.market_data import MarketDataManager

    manager = MarketDataManager()
    count = manager.delete_klines(symbol, bar)

    return jsonify({'status': 'success', 'msg': f'已删除 {count} 条数据'})


if __name__ == '__main__':
    from quant_engine.db import init_db
    init_db()
    app.run(debug=False, host='0.0.0.0', port=5002)
