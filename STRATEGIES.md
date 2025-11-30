# OKX 量化策略说明

## 策略列表

### 1. 网格交易策略 (grid_strategy.py) ⭐ 推荐新手使用

**策略原理：**
- 在当前价格上下设置网格
- 价格下跌时自动买入，上涨时自动卖出
- 通过赚取网格间的差价获利

**适用场景：**
- 震荡市场
- 横盘整理阶段

**参数说明：**
- `grid_size`: 网格间距，默认 2% (0.02)
- `base_order_size`: 每次交易金额，默认 100 USDT

**优点：**
- 逻辑简单，易于理解
- 适合震荡行情
- 风险相对可控

**缺点：**
- 单边行情可能表现不佳
- 需要一定的资金量

---

### 2. 双均线交叉策略 (ma_crossover.py)

**策略原理：**
- 计算短期均线（5周期）和长期均线（20周期）
- 短期均线上穿长期均线时买入（金叉）
- 短期均线下穿长期均线时卖出（死叉）

**适用场景：**
- 趋势明显的市场
- 中长期交易

**参数说明：**
- `short_period`: 短期均线周期，默认 5
- `long_period`: 长期均线周期，默认 20
- `order_amount`: 每次交易金额，默认 100 USDT

**优点：**
- 经典策略，历史验证
- 能够捕捉趋势
- 信号明确

**缺点：**
- 震荡市可能频繁交易
- 存在滞后性

---

### 3. 突破策略 (breakout_strategy.py)

**策略原理：**
- 跟踪最近20个周期的最高价和最低价
- 价格突破最高价时买入
- 价格跌破最低价或触发止盈止损时卖出

**适用场景：**
- 突破行情
- 波动较大的市场

**参数说明：**
- `lookback_period`: 回看周期，默认 20
- `stop_loss_ratio`: 止损比例，默认 5% (0.05)
- `take_profit_ratio`: 止盈比例，默认 10% (0.10)
- `order_amount`: 每次交易金额，默认 100 USDT

**优点：**
- 有止盈止损保护
- 能捕捉突破行情
- 风险控制较好

**缺点：**
- 假突破可能导致亏损
- 需要较好的市场判断

---

### 4. 原有策略 (TMV.py, gdxu.py, qqq.py, tqqq.py)

**注意事项：**
这些策略原本为股票市场设计，已进行除零错误修复，但可能不完全适合加密货币交易。

**主要问题：**
- 使用了保证金交易概念
- 参数可能不适合加密货币波动
- 缺少对OKX交易规则的适配

**建议：**
- 仅用于学习和参考
- 实盘前务必充分回测
- 建议使用新创建的策略

---

## 使用建议

### 新手入门
1. 先使用 **网格交易策略** 进行测试
2. 从小资金开始（建议 100-500 USDT）
3. 选择波动适中的交易对（如 BTC-USDT）

### 进阶使用
1. 根据市场情况选择合适的策略
2. 调整策略参数以适应不同市场
3. 结合多个策略分散风险

### 风险提示
⚠️ **重要提醒：**
- 所有策略仅供学习和参考
- 加密货币交易存在高风险
- 务必先进行充分的回测
- 实盘前从小资金开始测试
- 不要投入超过承受能力的资金

---

## 策略开发指南

### 基本框架
```python
class Strategy(StrategyBase):
    def initialize(self):
        # 初始化策略
        declare_strategy_type(AlgoStrategyType.SECURITY)
        self.trigger_symbols()
        self.global_variables()
    
    def trigger_symbols(self):
        # 定义交易标的
        self.symbol = declare_trig_symbol()
    
    def global_variables(self):
        # 定义全局变量
        pass
    
    def handle_data(self):
        # 核心交易逻辑
        try:
            # 获取当前价格
            current_price_value = current_price(symbol=self.symbol, price_type=THType.FTH)
            
            # 你的策略逻辑
            
        except Exception as e:
            print(f"策略执行错误: {e}")
```

### 可用函数
- `current_price(symbol, price_type)`: 获取当前价格
- `max_qty_to_sell(symbol)`: 获取可卖出数量
- `max_qty_to_buy_on_cash(symbol, order_type, price)`: 获取可买入数量（现金）
- `max_qty_to_buy_on_margin(symbol, order_type, price)`: 获取可买入数量（保证金）
- `place_limit(symbol, price, qty, side, time_in_force)`: 下限价单
- `position_pl_ratio(symbol, cost_price_model)`: 获取持仓盈亏比例

### 最佳实践
1. **异常处理**: 始终使用 try-except 包裹核心逻辑
2. **除零保护**: 在除法运算前检查分母是否为零
3. **数据验证**: 检查价格、数量等数据的有效性
4. **日志输出**: 使用 print 输出关键信息便于调试
5. **参数可配置**: 将关键参数定义为变量，便于调整

---

## 常见问题

**Q: 如何修改策略参数？**
A: 在策略文件的 `global_variables()` 方法中修改对应的参数值。

**Q: 策略执行频率是多少？**
A: 默认每5秒执行一次，可在 `strategy_framework.py` 中修改。

**Q: 如何停止运行中的策略？**
A: 目前需要重启应用来停止策略，后续版本会添加停止按钮。

**Q: 回测结果准确吗？**
A: 回测使用的是简化模型，实际交易会有滑点、手续费等因素，仅供参考。

**Q: 可以同时运行多个策略吗？**
A: 可以，但要注意资金分配和风险控制。
