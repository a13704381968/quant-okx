class Strategy(StrategyBase):
    def initialize(self):
        declare_strategy_type(AlgoStrategyType.SECURITY)
        self.trigger_symbols()
        self.global_variables()

    def trigger_symbols(self):
        self.symbol = declare_trig_symbol()

    def global_variables(self):
        # Strategy parameters
        self.base_order_usdt = show_variable(100.0, GlobalType.FLOAT)
        self.take_profit_ratio = show_variable(0.05, GlobalType.FLOAT)
        self.stop_loss_ratio = show_variable(0.03, GlobalType.FLOAT)
        self.position_inited = show_variable(False, GlobalType.INT)
        self.recent_high = show_variable(0.0, GlobalType.FLOAT)
        self.recent_low = show_variable(float('inf'), GlobalType.FLOAT)
        self.last_week_macd = show_variable(0.0, GlobalType.FLOAT)
        self.last_day_kdj = show_variable(0.0, GlobalType.FLOAT)
        self.current_position_side = show_variable(0, GlobalType.INT)  # 1 for long, -1 for short, 0 for no position

    def handle_data(self):
        try:
            self.execute_strategy()
        except Exception as e:
            print(f"Strategy error: {e}")

    def execute_strategy(self):
        crt_price = current_price(symbol=self.symbol, price_type=THType.FTH)
        if crt_price <= 0:
            print("Invalid price, skipping...")
            return

        # Update recent high and low
        self.recent_high = max(self.recent_high, crt_price)
        self.recent_low = min(self.recent_low, crt_price)

        # Get account information
        position_qty = max_qty_to_sell(symbol=self.symbol)
        max_buy_qty = max_qty_to_buy_on_cash(symbol=self.symbol, order_type=OrdType.LMT, price=crt_price)
        available_usdt = max_buy_qty * crt_price

        # Calculate position P&L
        if position_qty > 0:
            pl_ratio = position_pl_ratio(symbol=self.symbol, cost_price_model=CostPriceModel.AVG)
        else:
            pl_ratio = 0.0

        print(f"Price: {crt_price:.2f}, Position: {position_qty:.6f}, Available: {available_usdt:.2f} USDT, P&L: {pl_ratio:.2%}")

        # Simulate weekly MACD and daily KDJ signals (in real case, these would come from indicator calculations)
        # For demo purposes, we assume these values are updated externally or calculated from historical data
        # Here we just use placeholder logic - in practice, you'd implement or receive indicator values
        week_macd_value = self.get_weekly_macd()
        day_kdj_value = self.get_daily_kdj()

        # Detect MACD crossover on weekly (positive when MACD crosses above signal line)
        week_macd_cross_up = week_macd_value > 0 and self.last_week_macd <= 0
        week_macd_cross_down = week_macd_value < 0 and self.last_week_macd >= 0

        # Detect KDJ crossover on daily (positive when J crosses above D line)
        day_kdj_cross_up = day_kdj_value > 0 and self.last_day_kdj <= 0
        day_kdj_cross_down = day_kdj_value < 0 and self.last_day_kdj >= 0

        # Update last values
        self.last_week_macd = week_macd_value
        self.last_day_kdj = day_kdj_value

        # Take-profit and stop-loss checks
        if self.current_position_side == 1 and position_qty > 0:  # Long position
            if crt_price >= self.recent_high * (1 + self.take_profit_ratio):
                print("Long take-profit triggered")
                place_limit(symbol=self.symbol, price=crt_price, qty=position_qty, side=OrderSide.SELL, time_in_force=TimeInForce.GTC)
                self.current_position_side = 0
                self.recent_high = 0.0
                self.recent_low = float('inf')
                return
            if crt_price <= self.recent_low * (1 - self.stop_loss_ratio):
                print("Long stop-loss triggered")
                place_limit(symbol=self.symbol, price=crt_price, qty=position_qty, side=OrderSide.SELL, time_in_force=TimeInForce.GTC)
                self.current_position_side = 0
                self.recent_high = 0.0
                self.recent_low = float('inf')
                return

        elif self.current_position_side == -1 and position_qty > 0:  # Short position (assume we can short sell)
            if crt_price <= self.recent_low * (1 - self.take_profit_ratio):
                print("Short take-profit triggered")
                place_limit(symbol=self.symbol, price=crt_price, qty=position_qty, side=OrderSide.BUY, time_in_force=TimeInForce.GTC)
                self.current_position_side = 0
                self.recent_high = 0.0
                self.recent_low = float('inf')
                return
            if crt_price >= self.recent_high * (1 + self.stop_loss_ratio):
                print("Short stop-loss triggered")
                place_limit(symbol=self.symbol, price=crt_price, qty=position_qty, side=OrderSide.BUY, time_in_force=TimeInForce.GTC)
                self.current_position_side = 0
                self.recent_high = 0.0
                self.recent_low = float('inf')
                return

        # Entry logic
        # Long entry: Weekly MACD golden cross + Daily KDJ death cross
        if week_macd_cross_up and day_kdj_cross_down and self.current_position_side == 0:
            if available_usdt >= self.base_order_usdt:
                buy_qty = self.base_order_usdt / crt_price
                print(f"Long entry: Weekly MACD golden cross, Daily KDJ death cross at {crt_price:.2f}")
                place_limit(symbol=self.symbol, price=crt_price, qty=buy_qty, side=OrderSide.BUY, time_in_force=TimeInForce.GTC)
                self.current_position_side = 1
                self.recent_high = crt_price
                self.recent_low = crt_price
            else:
                print("Insufficient funds for long entry")

        # Short entry: Weekly MACD death cross + Daily KDJ golden cross
        elif week_macd_cross_down and day_kdj_cross_up and self.current_position_side == 0:
            # Note: In spot trading, shorting requires borrowing (not directly supported here unless margin/contract)
            # This assumes the platform supports short selling (or this is a contract strategy)
            if position_qty > 0:  # If we already have some base asset, we can sell (simulate short)
                sell_qty = min(position_qty, self.base_order_usdt / crt_price)
                print(f"Short entry: Weekly MACD death cross, Daily KDJ golden cross at {crt_price:.2f}")
                place_limit(symbol=self.symbol, price=crt_price, qty=sell_qty, side=OrderSide.SELL, time_in_force=TimeInForce.GTC)
                self.current_position_side = -1
                self.recent_high = crt_price
                self.recent_low = crt_price
            else:
                print("No available position to short sell (spot mode)")

        # Optional: Close long if conditions reverse
        elif self.current_position_side == 1 and position_qty > 0 and week_macd_cross_down and day_kdj_cross_up:
            print("Exit long due to condition reversal")
            place_limit(symbol=self.symbol, price=crt_price, qty=position_qty, side=OrderSide.SELL, time_in_force=TimeInForce.GTC)
            self.current_position_side = 0
            self.recent_high = 0.0
            self.recent_low = float('inf')

        # Optional: Close short if conditions reverse
        elif self.current_position_side == -1 and position_qty > 0 and week_macd_cross_up and day_kdj_cross_down:
            print("Exit short due to condition reversal")
            place_limit(symbol=self.symbol, price=crt_price, qty=position_qty, side=OrderSide.BUY, time_in_force=TimeInForce.GTC)
            self.current_position_side = 0
            self.recent_high = 0.0
            self.recent_low = float('inf')

    def get_weekly_macd(self):
        # Placeholder function - in real implementation, calculate or fetch weekly MACD histogram
        # For demo, return random-like behavior or use external data
        # In practice: use historical weekly data to compute MACD(12,26,9)
        # Here we simulate a value that can cross zero
        import random
        return random.uniform(-0.5, 0.5)  # Simulated MACD histogram value

    def get_daily_kdj(self):
        # Placeholder function - in real implementation, calculate or fetch daily KDJ J-D value
        # For demo, return random-like behavior or use external data
        # In practice: use historical daily data to compute KDJ(9,3,3) and return J-D
        import random
        return random.uniform(-10, 10)  # Simulated KDJ crossover signal