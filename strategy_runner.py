import sys
import os
import argparse
from quant_engine.config_loader import ConfigLoader
from quant_engine.okx_client import OKXClient
from quant_engine.strategy_framework import *

# Add current directory to sys.path
sys.path.append(os.getcwd())

def get_okx_client(config_loader):
    api_key = config_loader.get('OKX_API_KEY')
    secret_key = config_loader.get('OKX_SECRET_KEY')
    passphrase = config_loader.get('OKX_PASSPHRASE')
    base_url = config_loader.get('OKX_API_ENDPOINT', 'https://www.okx.com')
    proxy_url = config_loader.get('PROXY_URL')
    
    if api_key and secret_key and passphrase:
        return OKXClient(api_key, secret_key, passphrase, base_url, proxy_url)
    return None

def main():
    parser = argparse.ArgumentParser(description='Run a strategy')
    parser.add_argument('strategy_name', type=str, help='Name of the strategy file')
    parser.add_argument('symbol', type=str, help='Trading symbol')
    parser.add_argument('leverage', type=int, help='Leverage')
    parser.add_argument('interval', type=str, nargs='?', default='1H', help='K-line interval (1m, 5m, 15m, 1H, 4H, 1D)')

    args = parser.parse_args()

    strategy_name = args.strategy_name
    symbol = args.symbol
    leverage = args.leverage
    interval = args.interval

    # Map interval to sleep seconds
    interval_to_seconds = {
        '1m': 60, '5m': 300, '15m': 900,
        '1H': 3600, '4H': 14400, '1D': 86400
    }
    loop_interval = interval_to_seconds.get(interval, 3600)

    print(f"Runner starting: {strategy_name} on {symbol} with leverage {leverage}, interval {interval} ({loop_interval}s)")
    
    # Load Config
    CONFIG_PATH = os.path.join(os.getcwd(), '配置.txt')
    config_loader = ConfigLoader(CONFIG_PATH)
    client = get_okx_client(config_loader)
    
    if not client:
        print("Error: OKX Client configuration missing")
        sys.exit(1)
        
    path = os.path.join(os.getcwd(), 'strategy', strategy_name)
    if not os.path.exists(path):
        print(f"Error: Strategy file not found at {path}")
        sys.exit(1)
        
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
            # Set context for global functions
            set_context(client, symbol)

            # Set strategy name in context for logging
            from quant_engine.strategy_framework import StrategyContext
            StrategyContext.current_strategy_name = strategy_name

            strategy_instance = scope['Strategy'](client, symbol, strategy_name)
            # Set loop interval based on K-line period
            strategy_instance.loop_interval = loop_interval
            print(f"Strategy instance created. Running with interval {loop_interval}s...")
            strategy_instance.run()
        else:
            print(f"Error: No Strategy class found in {strategy_name}")
            sys.exit(1)
            
    except Exception as e:
        print(f"Error executing strategy: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

