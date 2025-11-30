import pandas as pd
import requests
import datetime
import math
from quant_engine.strategy_framework import *
from quant_engine.market_data import MarketDataManager

# 回测模式枚举
class BacktestMode:
    DATABASE = 'database'  # 使用数据库中的历史数据
    LIVE = 'live'          # 实时从OKX获取数据

class BacktestClient:
    def __init__(self, data):
        self.data = data
        self.current_index = 0
        self.orders = []
        self.balance = 10000.0 # Initial USDT
        self.positions = {} # symbol -> quantity

    def get_ticker(self, instId):
        # Return price at current timestamp
        if self.current_index < len(self.data):
            price = self.data.iloc[self.current_index]['close']
            return {'data': [{'last': str(price)}]}
        return {'data': [{'last': '0'}]}

    def get_account_balance(self):
        return {
            'code': '0',
            'data': [{
                'details': [{
                    'ccy': 'USDT',
                    'availEq': str(self.balance)
                }]
            }]
        }

    def get_positions(self):
        pos_data = []
        for symbol, qty in self.positions.items():
            if qty > 0:
                pos_data.append({
                    'instId': symbol,
                    'pos': str(qty)
                })
        return {
            'code': '0',
            'data': pos_data
        }

    def place_order(self, instId, tdMode, side, ordType, sz, px=None):
        price = float(px) if px else float(self.data.iloc[self.current_index]['close'])
        qty = float(sz)
        
        cost = price * qty
        
        if side == 'buy':
            if self.balance >= cost:
                self.balance -= cost
                self.positions[instId] = self.positions.get(instId, 0) + qty
                self.orders.append({
                    'time': self.data.iloc[self.current_index]['ts'],
                    'side': 'buy',
                    'price': price,
                    'qty': qty,
                    'balance': self.balance
                })
        elif side == 'sell':
            current_pos = self.positions.get(instId, 0)
            if current_pos >= qty:
                self.balance += cost
                self.positions[instId] = current_pos - qty
                self.orders.append({
                    'time': self.data.iloc[self.current_index]['ts'],
                    'side': 'sell',
                    'price': price,
                    'qty': qty,
                    'balance': self.balance
                })
        
        return {'code': '0', 'msg': 'success', 'data': [{'ordId': 'mock_id', 'state': 'filled'}]}

class BacktestEngine:
    def __init__(self, strategy_code, symbol, start_date, end_date, mode=BacktestMode.DATABASE, bar='1H', initial_balance=10000.0):
        self.strategy_code = strategy_code
        self.symbol = symbol
        self.start_date = start_date
        self.end_date = end_date
        self.mode = mode
        self.bar = bar
        self.initial_balance = initial_balance
        self.results = {}
        self.data_manager = MarketDataManager()

    def fetch_data_from_db(self):
        """从数据库获取K线数据"""
        df = self.data_manager.get_klines_from_db(
            self.symbol,
            self.bar,
            self.start_date,
            self.end_date
        )

        if df.empty:
            return None

        # 重命名列以匹配预期格式
        df = df.rename(columns={
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'vol': 'vol'
        })

        return df

    def fetch_data_live(self):
        """实时从OKX获取K线数据（分页获取完整数据）"""
        start_ts = int(pd.Timestamp(self.start_date).timestamp() * 1000)
        end_ts = int(pd.Timestamp(self.end_date).timestamp() * 1000)

        all_data = []
        current_after = end_ts
        max_batches = 500

        for _ in range(max_batches):
            url = f"https://www.okx.com/api/v5/market/history-candles?instId={self.symbol}&bar={self.bar}&limit=100&after={current_after}"
            try:
                response = requests.get(url)
                data = response.json()

                if data.get('code') != '0' or not data.get('data'):
                    break

                klines = data['data']
                if not klines:
                    break

                oldest_ts = int(klines[-1][0])
                if oldest_ts < start_ts:
                    klines = [k for k in klines if int(k[0]) >= start_ts]
                    all_data.extend(klines)
                    break

                all_data.extend(klines)
                current_after = oldest_ts

                import time
                time.sleep(0.1)

            except Exception as e:
                print(f"Error fetching data: {e}")
                break

        if not all_data:
            return None

        df = pd.DataFrame(all_data, columns=['ts', 'open', 'high', 'low', 'close', 'vol', 'volCcy', 'volCcyQuote', 'confirm'])
        df['ts'] = pd.to_numeric(df['ts'])
        for col in ['open', 'high', 'low', 'close', 'vol']:
            df[col] = pd.to_numeric(df[col])
        df = df.sort_values('ts').reset_index(drop=True)

        return df

    def fetch_data(self):
        """根据模式获取数据"""
        if self.mode == BacktestMode.DATABASE:
            df = self.fetch_data_from_db()
            if df is None or df.empty:
                return None, "数据库中没有该交易对的数据，请先同步历史数据"
            return df, None
        else:
            df = self.fetch_data_live()
            if df is None or df.empty:
                # 生成模拟数据作为后备
                print("⚠️ Warning: Using Dummy Data for Backtest")
                dates = pd.date_range(start=self.start_date, end=self.end_date, freq='H')
                prices = [10000 + 500 * math.sin(i/10) for i in range(len(dates))]
                df = pd.DataFrame({'ts': dates.astype(int) // 10**6, 'close': prices})
            return df, None

    def run(self):
        df, error = self.fetch_data()
        if error:
            return {'status': 'error', 'msg': error}
        if df is None or df.empty:
            return {'status': 'error', 'msg': 'No data found'}

        client = BacktestClient(df)
        client.balance = self.initial_balance

        # Prepare scope (similar to run_strategy_thread)
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
            'declare_trig_symbol': lambda: self.symbol,
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
            exec(self.strategy_code, scope)
            if 'Strategy' in scope:
                set_context(client, self.symbol)
                strategy = scope['Strategy'](client, self.symbol)
                strategy.initialize()

                # Run loop
                for i in range(len(df)):
                    client.current_index = i
                    strategy.handle_data()

                # Calculate final equity
                final_price = float(df.iloc[-1]['close'])
                equity = float(client.balance)
                for sym, qty in client.positions.items():
                    equity += float(qty) * final_price

                # 计算详细统计
                pnl = float(equity - self.initial_balance)
                pnl_ratio = float((pnl / self.initial_balance) * 100)

                # 确保订单数据可以JSON序列化
                serializable_orders = []
                for order in client.orders:
                    serializable_order = {}
                    for k, v in order.items():
                        if hasattr(v, 'item'):  # numpy类型
                            serializable_order[k] = v.item()
                        elif hasattr(v, '__float__'):
                            serializable_order[k] = float(v)
                        else:
                            serializable_order[k] = v
                    serializable_orders.append(serializable_order)

                return {
                    'status': 'success',
                    'initial_balance': float(self.initial_balance),
                    'final_equity': float(equity),
                    'pnl': float(pnl),
                    'pnl_ratio': float(pnl_ratio),
                    'total_orders': int(len(client.orders)),
                    'data_points': int(len(df)),
                    'mode': str(self.mode),
                    'bar': str(self.bar),
                    'orders': serializable_orders
                }
        except Exception as e:
            import traceback
            return {'status': 'error', 'msg': str(e), 'traceback': traceback.format_exc()}
