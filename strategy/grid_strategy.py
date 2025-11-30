class Strategy(StrategyBase):
    """
    简单网格交易策略 - 适用于OKX加密货币交易
    
    策略逻辑：
    1. 在当前价格上下设置网格
    2. 价格下跌时买入，上涨时卖出
    3. 赚取网格间的差价
    """
    
    def initialize(self):
        declare_strategy_type(AlgoStrategyType.SECURITY)
        self.trigger_symbols()
        self.global_variables()
    
    def trigger_symbols(self):
        self.symbol = declare_trig_symbol()
    
    def global_variables(self):
        # 网格参数
        self.grid_size = show_variable(0.02, GlobalType.FLOAT)  # 网格间距 2%
        self.base_order_size = show_variable(100.0, GlobalType.FLOAT)  # 基础下单金额 USDT
        
        # 状态变量
        self.last_buy_price = show_variable(0.0, GlobalType.FLOAT)
        self.last_sell_price = show_variable(0.0, GlobalType.FLOAT)
        self.position_count = show_variable(0, GlobalType.INT)
        
        # 初始化标志
        self.initialized = show_variable(False, GlobalType.INT)
    
    def handle_data(self):
        try:
            # 获取当前价格
            current_price_value = current_price(symbol=self.symbol, price_type=THType.FTH)
            
            if current_price_value <= 0:
                print("无效价格，跳过本次执行")
                return
            
            # 初始化参考价格
            if not self.initialized:
                self.last_buy_price = current_price_value
                self.last_sell_price = current_price_value
                self.initialized = True
                print(f"策略初始化完成，参考价格: {current_price_value}")
                return
            
            # 获取当前持仓
            current_position = max_qty_to_sell(symbol=self.symbol)
            
            # 获取可用资金
            available_cash = max_qty_to_buy_on_cash(symbol=self.symbol, order_type=OrdType.LMT, price=current_price_value)
            
            print(f"当前价格: {current_price_value}, 持仓: {current_position}, 可用资金: {available_cash}")
            
            # 买入逻辑：价格下跌超过网格间距
            if self.last_buy_price > 0:
                price_drop_ratio = (self.last_buy_price - current_price_value) / self.last_buy_price
                
                if price_drop_ratio >= self.grid_size and available_cash >= self.base_order_size:
                    # 计算买入数量
                    buy_qty = self.base_order_size / current_price_value
                    
                    if buy_qty > 0:
                        print(f"触发买入: 价格下跌 {price_drop_ratio*100:.2f}%, 买入数量: {buy_qty}")
                        place_limit(
                            symbol=self.symbol,
                            price=current_price_value,
                            qty=buy_qty,
                            side=OrderSide.BUY,
                            time_in_force=TimeInForce.GTC
                        )
                        self.last_buy_price = current_price_value
                        self.position_count += 1
            
            # 卖出逻辑：价格上涨超过网格间距且有持仓
            if self.last_sell_price > 0 and current_position > 0:
                price_rise_ratio = (current_price_value - self.last_sell_price) / self.last_sell_price
                
                if price_rise_ratio >= self.grid_size:
                    # 计算卖出数量（卖出部分持仓）
                    sell_qty = min(current_position * 0.5, self.base_order_size / current_price_value)
                    
                    if sell_qty > 0:
                        print(f"触发卖出: 价格上涨 {price_rise_ratio*100:.2f}%, 卖出数量: {sell_qty}")
                        place_limit(
                            symbol=self.symbol,
                            price=current_price_value,
                            qty=sell_qty,
                            side=OrderSide.SELL,
                            time_in_force=TimeInForce.GTC
                        )
                        self.last_sell_price = current_price_value
                        self.position_count -= 1
            
            # 更新参考价格
            if self.last_buy_price == 0:
                self.last_buy_price = current_price_value
            if self.last_sell_price == 0:
                self.last_sell_price = current_price_value
                
        except Exception as e:
            print(f"策略执行错误: {e}")
