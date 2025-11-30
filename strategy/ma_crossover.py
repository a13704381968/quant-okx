class Strategy(StrategyBase):
    """
    双均线交叉策略 - 适用于OKX加密货币交易
    
    策略逻辑：
    1. 计算短期和长期移动平均线
    2. 短期均线上穿长期均线时买入（金叉）
    3. 短期均线下穿长期均线时卖出（死叉）
    """
    
    def initialize(self):
        declare_strategy_type(AlgoStrategyType.SECURITY)
        self.trigger_symbols()
        self.global_variables()
    
    def trigger_symbols(self):
        self.symbol = declare_trig_symbol()
    
    def global_variables(self):
        # 均线参数
        self.short_period = show_variable(5, GlobalType.INT)  # 短期均线周期
        self.long_period = show_variable(20, GlobalType.INT)  # 长期均线周期
        
        # 价格历史
        self.price_history = []
        self.max_history = show_variable(25, GlobalType.INT)
        
        # 交易参数
        self.order_amount = show_variable(100.0, GlobalType.FLOAT)  # 每次交易金额 USDT
        
        # 状态变量
        self.last_signal = show_variable(0, GlobalType.INT)  # 0: 无, 1: 买入, -1: 卖出
        self.position_price = show_variable(0.0, GlobalType.FLOAT)
    
    def calculate_ma(self, prices, period):
        """计算移动平均线"""
        if len(prices) < period:
            return 0
        return sum(prices[-period:]) / period
    
    def handle_data(self):
        try:
            # 获取当前价格
            current_price_value = current_price(symbol=self.symbol, price_type=THType.FTH)
            
            if current_price_value <= 0:
                print("无效价格，跳过本次执行")
                return
            
            # 更新价格历史
            self.price_history.append(current_price_value)
            if len(self.price_history) > self.max_history:
                self.price_history.pop(0)
            
            # 需要足够的历史数据
            if len(self.price_history) < self.long_period:
                print(f"收集历史数据中... {len(self.price_history)}/{self.long_period}")
                return
            
            # 计算均线
            short_ma = self.calculate_ma(self.price_history, self.short_period)
            long_ma = self.calculate_ma(self.price_history, self.long_period)
            
            # 计算前一个周期的均线（用于判断交叉）
            prev_short_ma = self.calculate_ma(self.price_history[:-1], self.short_period)
            prev_long_ma = self.calculate_ma(self.price_history[:-1], self.long_period)
            
            print(f"当前价格: {current_price_value:.2f}, 短期MA: {short_ma:.2f}, 长期MA: {long_ma:.2f}")
            
            # 获取当前持仓和可用资金
            current_position = max_qty_to_sell(symbol=self.symbol)
            available_cash = max_qty_to_buy_on_cash(symbol=self.symbol, order_type=OrdType.LMT, price=current_price_value)
            
            # 金叉：短期均线上穿长期均线 -> 买入信号
            if prev_short_ma <= prev_long_ma and short_ma > long_ma and self.last_signal != 1:
                if available_cash >= self.order_amount:
                    buy_qty = self.order_amount / current_price_value
                    print(f"金叉信号！买入 {buy_qty:.4f} @ {current_price_value:.2f}")
                    place_limit(
                        symbol=self.symbol,
                        price=current_price_value,
                        qty=buy_qty,
                        side=OrderSide.BUY,
                        time_in_force=TimeInForce.GTC
                    )
                    self.last_signal = 1
                    self.position_price = current_price_value
            
            # 死叉：短期均线下穿长期均线 -> 卖出信号
            elif prev_short_ma >= prev_long_ma and short_ma < long_ma and self.last_signal != -1:
                if current_position > 0:
                    sell_qty = min(current_position, self.order_amount / current_price_value)
                    print(f"死叉信号！卖出 {sell_qty:.4f} @ {current_price_value:.2f}")
                    place_limit(
                        symbol=self.symbol,
                        price=current_price_value,
                        qty=sell_qty,
                        side=OrderSide.SELL,
                        time_in_force=TimeInForce.GTC
                    )
                    self.last_signal = -1
                    
                    # 计算收益
                    if self.position_price > 0:
                        profit_ratio = (current_price_value - self.position_price) / self.position_price * 100
                        print(f"本次交易收益率: {profit_ratio:.2f}%")
                        
        except Exception as e:
            print(f"策略执行错误: {e}")
