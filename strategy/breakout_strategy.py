class Strategy(StrategyBase):
    """
    突破策略 - 适用于OKX加密货币交易
    
    策略逻辑：
    1. 跟踪最近N个周期的最高价和最低价
    2. 价格突破最高价时买入
    3. 价格跌破最低价时卖出
    4. 设置止盈止损
    """
    
    def initialize(self):
        declare_strategy_type(AlgoStrategyType.SECURITY)
        self.trigger_symbols()
        self.global_variables()
    
    def trigger_symbols(self):
        self.symbol = declare_trig_symbol()
    
    def global_variables(self):
        # 突破参数
        self.lookback_period = show_variable(20, GlobalType.INT)  # 回看周期
        self.stop_loss_ratio = show_variable(0.05, GlobalType.FLOAT)  # 止损比例 5%
        self.take_profit_ratio = show_variable(0.10, GlobalType.FLOAT)  # 止盈比例 10%
        
        # 价格历史
        self.price_history = []
        
        # 交易参数
        self.order_amount = show_variable(100.0, GlobalType.FLOAT)  # 每次交易金额 USDT
        
        # 状态变量
        self.in_position = show_variable(False, GlobalType.INT)
        self.entry_price = show_variable(0.0, GlobalType.FLOAT)
        self.highest_high = show_variable(0.0, GlobalType.FLOAT)
        self.lowest_low = show_variable(0.0, GlobalType.FLOAT)
    
    def handle_data(self):
        try:
            # 获取当前价格
            current_price_value = current_price(symbol=self.symbol, price_type=THType.FTH)
            
            if current_price_value <= 0:
                print("无效价格，跳过本次执行")
                return
            
            # 更新价格历史
            self.price_history.append(current_price_value)
            if len(self.price_history) > self.lookback_period:
                self.price_history.pop(0)
            
            # 需要足够的历史数据
            if len(self.price_history) < self.lookback_period:
                print(f"收集历史数据中... {len(self.price_history)}/{self.lookback_period}")
                return
            
            # 计算最高价和最低价
            self.highest_high = max(self.price_history[:-1])  # 不包括当前价格
            self.lowest_low = min(self.price_history[:-1])
            
            print(f"当前价格: {current_price_value:.2f}, 最高: {self.highest_high:.2f}, 最低: {self.lowest_low:.2f}")
            
            # 获取当前持仓
            current_position = max_qty_to_sell(symbol=self.symbol)
            self.in_position = current_position > 0
            
            # 如果持仓，检查止盈止损
            if self.in_position and self.entry_price > 0:
                profit_ratio = (current_price_value - self.entry_price) / self.entry_price
                
                # 止损
                if profit_ratio <= -self.stop_loss_ratio:
                    print(f"触发止损！亏损 {profit_ratio*100:.2f}%")
                    place_limit(
                        symbol=self.symbol,
                        price=current_price_value,
                        qty=current_position,
                        side=OrderSide.SELL,
                        time_in_force=TimeInForce.GTC
                    )
                    self.in_position = False
                    return
                
                # 止盈
                if profit_ratio >= self.take_profit_ratio:
                    print(f"触发止盈！盈利 {profit_ratio*100:.2f}%")
                    place_limit(
                        symbol=self.symbol,
                        price=current_price_value,
                        qty=current_position,
                        side=OrderSide.SELL,
                        time_in_force=TimeInForce.GTC
                    )
                    self.in_position = False
                    return
                
                # 跌破最低价卖出
                if current_price_value < self.lowest_low:
                    print(f"价格跌破最低价 {self.lowest_low:.2f}，卖出")
                    place_limit(
                        symbol=self.symbol,
                        price=current_price_value,
                        qty=current_position,
                        side=OrderSide.SELL,
                        time_in_force=TimeInForce.GTC
                    )
                    self.in_position = False
            
            # 如果无持仓，检查突破买入
            elif not self.in_position:
                available_cash = max_qty_to_buy_on_cash(symbol=self.symbol, order_type=OrdType.LMT, price=current_price_value)
                
                # 突破最高价买入
                if current_price_value > self.highest_high and available_cash >= self.order_amount:
                    buy_qty = self.order_amount / current_price_value
                    print(f"价格突破最高价 {self.highest_high:.2f}，买入 {buy_qty:.4f}")
                    place_limit(
                        symbol=self.symbol,
                        price=current_price_value,
                        qty=buy_qty,
                        side=OrderSide.BUY,
                        time_in_force=TimeInForce.GTC
                    )
                    self.in_position = True
                    self.entry_price = current_price_value
                    
        except Exception as e:
            print(f"策略执行错误: {e}")
