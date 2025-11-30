class Strategy(StrategyBase):
    """
    Momentum Grid Strategy for OKX Crypto Trading
    Exponential position sizing based on price momentum
    """

    def initialize(self):
        declare_strategy_type(AlgoStrategyType.SECURITY)
        self.trigger_symbols()
        self.global_variables()

    def trigger_symbols(self):
        self.symbol = declare_trig_symbol()

    def global_variables(self):
        self.recent_low = show_variable(0.0, GlobalType.FLOAT)
        self.recent_high = show_variable(0.0, GlobalType.FLOAT)
        self.last_sell_price = show_variable(0.0, GlobalType.FLOAT)
        self.last_buy_price = show_variable(0.0, GlobalType.FLOAT)
        self.sell_count = show_variable(0, GlobalType.INT)
        self.buy_count = show_variable(0, GlobalType.INT)
        self.base_order_usdt = show_variable(100.0, GlobalType.FLOAT)
        self.buy_threshold = show_variable(0.02, GlobalType.FLOAT)
        self.sell_threshold = show_variable(0.03, GlobalType.FLOAT)
        self.initialized = show_variable(False, GlobalType.INT)

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
        # max_qty_to_buy_on_cash returns USDT balance directly, no need to multiply by price
        available_usdt = max_qty_to_buy_on_cash(symbol=self.symbol, order_type=OrdType.LMT, price=crt_price)

        print(f"Price: {crt_price:.2f}, Position: {position_qty:.6f}, Available: {available_usdt:.2f} USDT")

        if not self.initialized:
            self.recent_high = crt_price
            self.recent_low = crt_price
            self.initialized = True
            if position_qty <= 0 and available_usdt >= self.base_order_usdt:
                init_qty = (available_usdt * 0.15) / crt_price
                print(f"Init position: BUY {init_qty:.6f} @ {crt_price:.2f}")
                place_limit(symbol=self.symbol, price=crt_price, qty=init_qty,
                           side=OrderSide.BUY, time_in_force=TimeInForce.GTC)
                self.last_buy_price = crt_price
                self.buy_count = 1
            return

        print(f"Tracking - Low: {self.recent_low:.2f}, High: {self.recent_high:.2f}")

        if self.recent_high > 0:
            drop_ratio = (self.recent_high - crt_price) / self.recent_high
            if drop_ratio >= self.buy_threshold and available_usdt >= self.base_order_usdt:
                momentum_mult = 1.0
                if self.last_sell_price > 0 and crt_price > 0:
                    price_diff = abs(self.last_sell_price - crt_price) / crt_price
                    momentum_mult = min(1.0 + (price_diff * 5) ** (self.buy_count + 1), 5.0)
                
                buy_usdt = min(self.base_order_usdt * momentum_mult, available_usdt * 0.3)
                buy_qty = buy_usdt / crt_price
                
                print(f"Momentum buy! Drop: {drop_ratio*100:.2f}%, Mult: {momentum_mult:.2f}x, BUY {buy_qty:.6f} @ {crt_price:.2f}")
                place_limit(symbol=self.symbol, price=crt_price, qty=buy_qty,
                           side=OrderSide.BUY, time_in_force=TimeInForce.GTC)
                self.last_buy_price = crt_price
                self.recent_high = crt_price
                self.recent_low = crt_price
                self.buy_count += 1
                self.sell_count = 0
                return

        if self.recent_low > 0 and position_qty > 0:
            rise_ratio = (crt_price - self.recent_low) / self.recent_low
            if rise_ratio >= self.sell_threshold:
                momentum_mult = 1.0
                if self.last_buy_price > 0:
                    price_diff = abs(crt_price - self.last_buy_price) / self.last_buy_price
                    momentum_mult = min(1.0 + (price_diff * 5) ** (self.sell_count + 1), 5.0)
                
                sell_qty = min(position_qty * 0.1 * momentum_mult, position_qty * 0.4)
                
                print(f"Momentum sell! Rise: {rise_ratio*100:.2f}%, Mult: {momentum_mult:.2f}x, SELL {sell_qty:.6f} @ {crt_price:.2f}")
                place_limit(symbol=self.symbol, price=crt_price, qty=sell_qty,
                           side=OrderSide.SELL, time_in_force=TimeInForce.GTC)
                self.last_sell_price = crt_price
                self.recent_low = crt_price
                self.recent_high = crt_price
                self.sell_count += 1
                self.buy_count = 0
                return

        if crt_price < self.recent_low or self.recent_low == 0:
            self.recent_low = crt_price
        if crt_price > self.recent_high or self.recent_high == 0:
            self.recent_high = crt_price

