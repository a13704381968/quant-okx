class Strategy(StrategyBase):
    """
    EMA黄金交叉策略 - 适用于OKX加密货币交易
    
    策略逻辑：
    1. 使用两个EMA指标：快线(短期)和慢线(长期)
    2. 当快线上穿慢线时产生黄金交叉，买入信号
    3. 当快线下穿慢线时产生死亡交叉，卖出信号
    4. 设置止盈止损保护利润和控制风险
    """
    
    def initialize(self):
        declare_strategy_type(AlgoStrategyType.SECURITY)
        self.trigger_symbols()
        self.global_variables()
    
    def trigger_symbols(self):
        self.symbol = declare_trig_symbol()
    
    def global_variables(self):
        # EMA参数
        self.fast_ema_period = show_variable(12, GlobalType.INT)  # 快线EMA周期
        self.slow_ema_period = show_variable(26, GlobalType.INT)  # 慢线EMA周期
        
        # 风险管理参数
        self.stop_loss_ratio = show_variable(0.05, GlobalType.FLOAT)  # 止损比例 5%
        self.take_profit_ratio = show_variable(0.10, GlobalType.FLOAT)  # 止盈比例 10%
        
        # 价格历史
        self.price_history = []
        
        # EMA计算历史
        self.fast_ema_history = []
        self.slow_ema_history = []
        
        # 交易参数
        self.order_amount = show_variable(100.0, GlobalType.FLOAT)  # 每次交易金额 USDT
        
        # 状态变量
        self.in_position = show_variable(False, GlobalType.INT)
        self.entry_price = show_variable(0.0, GlobalType.FLOAT)
        self.prev_fast_ema = show_variable(0.0, GlobalType.FLOAT)
        self.prev_slow_ema = show_variable(0.0, GlobalType.FLOAT)
    
    def calculate_ema(self, prices, period, prev_ema=None):
        """
        计算指数移动平均线(EMA)
        
        Args:
            prices: 价格列表
            period: EMA周期
            prev_ema: 前一个EMA值（用于增量计算）
            
        Returns:
            EMA值
        """
        if len(prices) < period:
            return None
        
        # 计算平滑系数
        alpha = 2.0 / (period + 1)
        
        if prev_ema is None:
            # 首次计算，使用简单移动平均作为初始值
            sma = sum(prices[-period:]) / period
            return sma
        else:
            # 增量计算EMA
            current_price = prices[-1]
            return (current_price - prev_ema) * alpha + prev_ema
    
    def handle_data(self):
        try:
            # 获取当前价格
            current_price_value = current_price(symbol=self.symbol, price_type=THType.FTH)
            
            if current_price_value <= 0:
                print("无效价格，跳过本次执行")
                return
            
            # 更新价格历史
            self.price_history.append(current_price_value)
            
            # 需要足够的历史数据来计算慢线EMA
            min_data_required = max(self.fast_ema_period, self.slow_ema_period)
            if len(self.price_history) < min_data_required:
                print(f"收集历史数据中... {len(self.price_history)}/{min_data_required}")
                return
            
            # 计算EMA值
            # 获取前一个EMA值
            prev_fast = self.prev_fast_ema if len(self.fast_ema_history) > 0 else None
            prev_slow = self.prev_slow_ema if len(self.slow_ema_history) > 0 else None
            
            # 计算当前EMA
            fast_ema = self.calculate_ema(self.price_history, self.fast_ema_period, prev_fast)
            slow_ema = self.calculate_ema(self.price_history, self.slow_ema_period, prev_slow)
            
            if fast_ema is None or slow_ema is None:
                print("EMA计算失败，跳过本次执行")
                return
            
            # 保存EMA历史
            self.fast_ema_history.append(fast_ema)
            self.slow_ema_history.append(slow_ema)
            
            # 限制历史数据长度
            max_history = 100
            if len(self.fast_ema_history) > max_history:
                self.fast_ema_history.pop(0)
                self.slow_ema_history.pop(0)
            
            # 更新前值
            self.prev_fast_ema = fast_ema
            self.prev_slow_ema = slow_ema
            
            print(f"当前价格: {current_price_value:.2f}, 快线EMA({self.fast_ema_period}): {fast_ema:.2f}, 慢线EMA({self.slow_ema_period}): {slow_ema:.2f}")
            
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
            
            # 需要至少2个EMA值来判断交叉
            if len(self.fast_ema_history) >= 2 and len(self.slow_ema_history) >= 2:
                # 获取前一个EMA值
                prev_fast = self.fast_ema_history[-2]
                prev_slow = self.slow_ema_history[-2]
                
                # 检查黄金交叉（买入信号）
                if not self.in_position:
                    # 黄金交叉：前一个周期快线在慢线下方，当前周期快线在慢线上方
                    if prev_fast <= prev_slow and fast_ema > slow_ema:
                        available_cash = max_qty_to_buy_on_cash(symbol=self.symbol, order_type=OrdType.LMT, price=current_price_value)
                        
                        if available_cash >= self.order_amount:
                            buy_qty = self.order_amount / current_price_value
                            print(f"EMA黄金交叉！快线({fast_ema:.2f})上穿慢线({slow_ema:.2f})，买入 {buy_qty:.4f}")
                            place_limit(
                                symbol=self.symbol,
                                price=current_price_value,
                                qty=buy_qty,
                                side=OrderSide.BUY,
                                time_in_force=TimeInForce.GTC
                            )
                            self.in_position = True
                            self.entry_price = current_price_value
                
                # 检查死亡交叉（卖出信号）
                elif self.in_position:
                    # 死亡交叉：前一个周期快线在慢线上方，当前周期快线在慢线下方
                    if prev_fast >= prev_slow and fast_ema < slow_ema:
                        print(f"EMA死亡交叉！快线({fast_ema:.2f})下穿慢线({slow_ema:.2f})，卖出")
                        place_limit(
                            symbol=self.symbol,
                            price=current_price_value,
                            qty=current_position,
                            side=OrderSide.SELL,
                            time_in_force=TimeInForce.GTC
                        )
                        self.in_position = False
            
            # 如果EMA历史不足2个，使用当前值简单判断
            elif len(self.fast_ema_history) == 1:
                # 简单判断：快线>慢线时买入（如果无持仓）
                if not self.in_position and fast_ema > slow_ema:
                    available_cash = max_qty_to_buy_on_cash(symbol=self.symbol, order_type=OrdType.LMT, price=current_price_value)
                    
                    if available_cash >= self.order_amount:
                        buy_qty = self.order_amount / current_price_value
                        print(f"快线在慢线上方，买入 {buy_qty:.4f}")
                        place_limit(
                            symbol=self.symbol,
                            price=current_price_value,
                            qty=buy_qty,
                            side=OrderSide.BUY,
                            time_in_force=TimeInForce.GTC
                        )
                        self.in_position = True
                        self.entry_price = current_price_value
                
                # 简单判断：快线<慢线时卖出（如果持仓）
                elif self.in_position and fast_ema < slow_ema:
                    print(f"快线在慢线下方，卖出")
                    place_limit(
                        symbol=self.symbol,
                        price=current_price_value,
                        qty=current_position,
                        side=OrderSide.SELL,
                        time_in_force=TimeInForce.GTC
                    )
                    self.in_position = False
                    
        except Exception as e:
            print(f"策略执行错误: {e}")
            import traceback
            traceback.print_exc()