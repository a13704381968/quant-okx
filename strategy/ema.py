class Strategy(StrategyBase):
    def initialize(self):
        declare_strategy_type(AlgoStrategyType.SECURITY)
        self.trigger_symbols()
        self.global_variables()
        self.init_indicators()

    def trigger_symbols(self):
        self.symbol = declare_trig_symbol()

    def global_variables(self):
        self.fast_ema_period = show_variable(12, GlobalType.INT)
        self.slow_ema_period = show_variable(26, GlobalType.INT)
        self.base_order_usdt = show_variable(100.0, GlobalType.FLOAT)
        self.take_profit_pct = show_variable(0.05, GlobalType.FLOAT)
        self.stop_loss_pct = show_variable(0.03, GlobalType.FLOAT)
        self.trailing_stop_pct = show_variable(0.02, GlobalType.FLOAT)
        
        self.position_entry_price = show_variable(0.0, GlobalType.FLOAT)
        self.position_peak_price = show_variable(0.0, GlobalType.FLOAT)
        self.indicators_initialized = show_variable(False, GlobalType.INT)

    def init_indicators(self):
        self.fast_ema_values = []
        self.slow_ema_values = []
        self.price_history = []
        self.golden_cross_flag = False
        self.death_cross_flag = False
        self.entry_price = 0.0

    def calculate_ema(self, prices, period):
        if len(prices) < period:
            return None
        
        multiplier = 2.0 / (period + 1)
        ema = sum(prices[:period]) / period
        
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        
        return ema

    def handle_data(self):
        try:
            self.execute_strategy()
        except Exception as e:
            print(f"Strategy error: {e}")

    def execute_strategy(self):
        crt_price = current_price(symbol=self.symbol, price_type=THType.FTH)
        if crt_price <= 0:
            return

        position_qty = max_qty_to_sell(symbol=self.symbol)
        max_buy_qty = max_qty_to_buy_on_cash(symbol=self.symbol, order_type=OrdType.LMT, price=crt_price)
        available_usdt = max_buy_qty * crt_price

        print(f"Price: {crt_price:.2f}, Position: {position_qty:.6f}, Available: {available_usdt:.2f} USDT")

        self.price_history.append(crt_price)
        
        if len(self.price_history) > max(self.fast_ema_period, self.slow_ema_period):
            fast_ema = self.calculate_ema(self.price_history, self.fast_ema_period)
            slow_ema = self.calculate_ema(self.price_history, self.slow_ema_period)
            
            if fast_ema is not None and slow_ema is not None:
                self.fast_ema_values.append(fast_ema)
                self.slow_ema_values.append(slow_ema)
                
                if len(self.fast_ema_values) > 1 and len(self.slow_ema_values) > 1:
                    prev_fast_ema = self.fast_ema_values[-2]
                    prev_slow_ema = self.slow_ema_values[-2]
                    
                    golden_cross = prev_fast_ema <= prev_slow_ema and fast_ema > slow_ema
                    death_cross = prev_fast_ema >= prev_slow_ema and fast_ema < slow_ema
                    
                    if golden_cross and not self.golden_cross_flag:
                        print(f"Golden Cross detected! Fast EMA: {fast_ema:.2f}, Slow EMA: {slow_ema:.2f}")
                        self.golden_cross_flag = True
                        self.death_cross_flag = False
                        
                        if position_qty <= 0 and available_usdt >= self.base_order_usdt:
                            buy_qty = self.base_order_usdt / crt_price
                            place_limit(symbol=self.symbol, price=crt_price, qty=buy_qty, 
                                       side=OrderSide.BUY, time_in_force=TimeInForce.GTC)
                            print(f"Buy order placed: {buy_qty:.6f} at {crt_price:.2f}")
                            self.entry_price = crt_price
                            self.position_peak_price = crt_price
                    
                    elif death_cross and not self.death_cross_flag:
                        print(f"Death Cross detected! Fast EMA: {fast_ema:.2f}, Slow EMA: {slow_ema:.2f}")
                        self.death_cross_flag = True
                        self.golden_cross_flag = False
                        
                        if position_qty > 0:
                            sell_qty = position_qty
                            place_limit(symbol=self.symbol, price=crt_price, qty=sell_qty, 
                                       side=OrderSide.SELL, time_in_force=TimeInForce.GTC)
                            print(f"Sell order placed: {sell_qty:.6f} at {crt_price:.2f}")
                            self.entry_price = 0.0
                            self.position_peak_price = 0.0
                
                if position_qty > 0:
                    pl_ratio = position_pl_ratio(symbol=self.symbol, cost_price_model=CostPriceModel.AVG)
                    
                    if self.entry_price > 0:
                        profit_pct = (crt_price - self.entry_price) / self.entry_price
                        
                        if crt_price > self.position_peak_price:
                            self.position_peak_price = crt_price
                        
                        trailing_stop_price = self.position_peak_price * (1 - self.trailing_stop_pct)
                        take_profit_price = self.entry_price * (1 + self.take_profit_pct)
                        stop_loss_price = self.entry_price * (1 - self.stop_loss_pct)
                        
                        print(f"Position P&L: {pl_ratio:.2%}, Entry: {self.entry_price:.2f}, Current: {crt_price:.2f}")
                        print(f"Take Profit: {take_profit_price:.2f}, Stop Loss: {stop_loss_price:.2f}, Trailing Stop: {trailing_stop_price:.2f}")
                        
                        if crt_price >= take_profit_price:
                            sell_qty = position_qty
                            place_limit(symbol=self.symbol, price=crt_price, qty=sell_qty, 
                                       side=OrderSide.SELL, time_in_force=TimeInForce.GTC)
                            print(f"Take profit triggered at {crt_price:.2f}")
                            self.entry_price = 0.0
                            self.position_peak_price = 0.0
                        
                        elif crt_price <= stop_loss_price:
                            sell_qty = position_qty
                            place_limit(symbol=self.symbol, price=crt_price, qty=sell_qty, 
                                       side=OrderSide.SELL, time_in_force=TimeInForce.GTC)
                            print(f"Stop loss triggered at {crt_price:.2f}")
                            self.entry_price = 0.0
                            self.position_peak_price = 0.0
                        
                        elif crt_price <= trailing_stop_price:
                            sell_qty = position_qty
                            place_limit(symbol=self.symbol, price=crt_price, qty=sell_qty, 
                                       side=OrderSide.SELL, time_in_force=TimeInForce.GTC)
                            print(f"Trailing stop triggered at {crt_price:.2f}")
                            self.entry_price = 0.0
                            self.position_peak_price = 0.0
        
        if len(self.price_history) > 100:
            self.price_history = self.price_history[-100:]
            self.fast_ema_values = self.fast_ema_values[-50:]
            self.slow_ema_values = self.slow_ema_values[-50:]