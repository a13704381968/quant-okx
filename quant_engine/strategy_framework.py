from enum import Enum
import time

class AlgoStrategyType(Enum):
    SECURITY = 1

class GlobalType(Enum):
    FLOAT = 1
    INT = 2

class THType(Enum):
    FTH = 1

class OrderSide(Enum):
    BUY = 'buy'
    SELL = 'sell'

class TimeInForce(Enum):
    GTC = 'gtc'
    DAY = 'day'

class OrdType(Enum):
    LMT = 'limit'
    MKT = 'market'

class CostPriceModel(Enum):
    AVG = 1

class StrategyBase:
    def __init__(self, client, symbol, strategy_name=None):
        self.client = client
        self.symbol = symbol
        self.is_running = False
        self.strategy_name = strategy_name or self.__class__.__name__
        self.last_heartbeat = time.time()
        self.loop_interval = 30  # Default interval, can be overridden
        
    def log_event(self, level, event_type, message, data=None):
        """Log a strategy event to database"""
        try:
            from quant_engine.db import log_strategy_event
            log_strategy_event(self.strategy_name, level, event_type, message, data)
        except Exception as e:
            print(f"Failed to log event: {e}")
    
    def log_signal(self, signal_type, message, data=None):
        """Log a trading signal"""
        self.log_event('INFO', 'SIGNAL', f"{signal_type}: {message}", data)
    
    def update_heartbeat(self):
        """Update strategy heartbeat in database"""
        try:
            from quant_engine.db import update_strategy_status
            update_strategy_status(self.strategy_name, 'RUNNING')
        except Exception as e:
            print(f"Failed to update heartbeat: {e}")

    def initialize(self):
        pass

    def handle_data(self):
        pass

    def run(self):
        self.log_event('INFO', 'START', f'Strategy {self.strategy_name} started on {self.symbol}')
        
        try:
            self.initialize()
            self.is_running = True
            
            while self.is_running:
                try:
                    # Update heartbeat every 30 seconds
                    current_time = time.time()
                    if current_time - self.last_heartbeat > 30:
                        self.update_heartbeat()
                        self.log_event('INFO', 'HEARTBEAT', 'Strategy is running')
                        self.last_heartbeat = current_time
                    
                    self.handle_data()
                except Exception as e:
                    error_msg = f"Error in strategy loop: {e}"
                    print(error_msg)
                    self.log_event('ERROR', 'ERROR', error_msg)
                    
                time.sleep(self.loop_interval)
                
        except Exception as e:
            error_msg = f"Fatal error in strategy: {e}"
            print(error_msg)
            self.log_event('ERROR', 'ERROR', error_msg)
            from quant_engine.db import update_strategy_status
            update_strategy_status(self.strategy_name, 'ERROR', error_msg)
        finally:
            self.log_event('INFO', 'STOP', f'Strategy {self.strategy_name} stopped')

    def stop(self):
        self.is_running = False

# Helper functions to be injected
def declare_strategy_type(type):
    print(f"Declared strategy type: {type}")

def declare_trig_symbol():
    return "BTC-USDT" # Default or passed from runner

def show_variable(val, type):
    return val

def current_price(symbol, price_type):
    # This should call the client to get price
    # For now, we need a way to access the client from these global functions
    # We might need to set a global context
    return 95000.0 # Mock for now, should be real

def max_qty_to_sell(symbol):
    return 1.0

def max_qty_to_buy_on_cash(symbol, order_type, price):
    return 1.0

def position_pl_ratio(symbol, cost_price_model):
    return 0.1

def max_qty_to_buy_on_margin(symbol, order_type, price):
    # Mock implementation - returns available margin for buying
    return 1000.0

def place_limit(symbol, price, qty, side, time_in_force):
    print(f"Placing limit order: {side} {qty} {symbol} @ {price}")
    # Real implementation would call client.place_order

def ceil(x):
    import math
    return math.ceil(x)

# Context manager to handle global context for strategies
class StrategyContext:
    current_client = None
    current_symbol = None
    current_strategy_name = 'unknown'

def set_context(client, symbol, strategy_name=None):
    StrategyContext.current_client = client
    StrategyContext.current_symbol = symbol
    if strategy_name:
        StrategyContext.current_strategy_name = strategy_name

# Redefine functions to use context
def current_price(symbol, price_type):
    if StrategyContext.current_client:
        ticker = StrategyContext.current_client.get_ticker(symbol)
        if 'data' in ticker and ticker['data']:
            return float(ticker['data'][0]['last'])
    return 0.0

def place_limit(symbol, price, qty, side, time_in_force):
    strategy_name = getattr(StrategyContext, 'current_strategy_name', 'unknown')
    from quant_engine.db import log_trade, log_strategy_event

    if not StrategyContext.current_client:
        error_msg = f"No client context available for order: {side} {qty} {symbol} @ {price}"
        print(f"[ORDER ERROR] {error_msg}")
        log_strategy_event(strategy_name, 'ERROR', 'ORDER', error_msg)
        return None

    # Convert enum to string if needed
    side_str = side.value if isinstance(side, Enum) else side

    # Determine trade mode and quantity format based on instrument type
    # SWAP/FUTURES: use 'cross', qty is in contracts (integer for BTC-USDT-SWAP, 1 contract = 0.01 BTC)
    # SPOT: use 'cash', qty is in base currency (e.g., BTC)
    if '-SWAP' in symbol or '-FUTURES' in symbol:
        td_mode = 'cross'  # Use cross margin for derivatives
        # For SWAP, quantity must be integer (number of contracts)
        # BTC-USDT-SWAP: 1 contract = 0.01 BTC, so convert qty to contracts
        if 'BTC-USDT-SWAP' in symbol:
            # qty is in BTC, convert to contracts (1 contract = 0.01 BTC = 100 USD face value)
            contracts = int(qty * 100)  # qty BTC * 100 = contracts
            if contracts < 1:
                contracts = 1  # Minimum 1 contract
            qty = contracts
        else:
            # For other SWAP, round to integer
            qty = max(1, int(qty))
    else:
        td_mode = 'cash'   # Use cash for spot trading
        # For spot, ensure minimum order size
        # BTC-USDT minimum is usually 0.00001 BTC
        qty = max(0.00001, float(qty))

    try:
        print(f"[ORDER] Placing {side_str} order: {qty} {symbol} @ {price} (tdMode={td_mode})")

        result = StrategyContext.current_client.place_order(
            instId=symbol,
            tdMode=td_mode,
            side=side_str,
            ordType='limit',
            sz=qty,
            px=price
        )

        print(f"[ORDER] API Response: {result}")

        # Parse response
        order_id = None
        status = 'FAILED'
        error_msg = None

        if result:
            if result.get('code') == '0' and result.get('data'):
                order_id = result['data'][0].get('ordId')
                sMsg = result['data'][0].get('sMsg', '')
                sCode = result['data'][0].get('sCode', '')

                if sCode == '0':
                    status = 'SUBMITTED'
                    print(f"[ORDER SUCCESS] Order ID: {order_id}")
                else:
                    status = 'FAILED'
                    error_msg = sMsg
                    print(f"[ORDER FAILED] {sMsg}")
            else:
                error_msg = result.get('msg', 'Unknown error')
                print(f"[ORDER ERROR] API error: {error_msg}")

        # Log the trade
        log_trade(
            strategy_name=strategy_name,
            symbol=symbol,
            side=side_str,
            order_type='limit',
            price=price,
            quantity=qty,
            order_id=order_id,
            status=status
        )

        if status == 'SUBMITTED':
            log_strategy_event(
                strategy_name=strategy_name,
                level='INFO',
                event_type='ORDER',
                message=f'Order submitted: {side_str} {qty} @ {price}',
                data={'order_id': order_id, 'symbol': symbol, 'price': price, 'qty': qty}
            )
        else:
            log_strategy_event(
                strategy_name=strategy_name,
                level='ERROR',
                event_type='ORDER',
                message=f'Order failed: {error_msg}',
                data={'symbol': symbol, 'price': price, 'qty': qty, 'side': side_str, 'response': str(result)}
            )

        return result

    except Exception as e:
        error_msg = f"Exception placing order: {e}"
        print(f"[ORDER EXCEPTION] {error_msg}")
        log_strategy_event(
            strategy_name=strategy_name,
            level='ERROR',
            event_type='ORDER',
            message=error_msg,
            data={'symbol': symbol, 'price': price, 'qty': qty, 'side': side_str}
        )
        return None

def max_qty_to_buy_on_cash(symbol, order_type, price):
    """
    Returns the available cash (USDT) for buying.
    Note: Despite the name 'qty', this returns the quote currency amount (USDT) 
    based on the usage in strategies.
    """
    if StrategyContext.current_client:
        try:
            balance_res = StrategyContext.current_client.get_account_balance()
            if balance_res.get('code') == '0' and balance_res.get('data'):
                details = balance_res['data'][0].get('details', [])
                for d in details:
                    if d.get('ccy') == 'USDT':
                        return float(d.get('availEq', 0))
        except Exception as e:
            print(f"Error getting balance: {e}")
    return 0.0

def max_qty_to_sell(symbol):
    """Returns the available quantity of the symbol for selling."""
    if StrategyContext.current_client:
        try:
            pos_res = StrategyContext.current_client.get_positions()
            if pos_res.get('code') == '0' and pos_res.get('data'):
                for pos in pos_res['data']:
                    if pos.get('instId') == symbol:
                        # For net mode, pos can be positive (long) or negative (short)
                        # For cash/spot, it's usually positive
                        qty = float(pos.get('pos', 0))
                        # If we are in long/short mode, we might need to check side
                        # But for simple spot/cash, pos is what we have
                        return max(0, qty)
        except Exception as e:
            print(f"Error getting positions: {e}")
    return 0.0
