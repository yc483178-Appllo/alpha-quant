# Alpha-Genesis V7.0 - 专业级回测引擎详细设计

## 2.2 专业级回测引擎

### 2.2.1 A股规则全适配

**精准模拟A股全规则体系**:

| 规则类型 | 模拟内容 | 实现细节 |
|----------|----------|----------|
| **T+1制度** | 当日买入不可卖出 | 持仓状态跟踪 + 可卖数量计算 |
| **涨跌停限制** | ±10%(主板)、±20%(科创/创业)、±5%(ST) | 动态价格边界检查 |
| **停牌/退市** | 不可交易股票过滤 | 交易日历同步 + 状态监控 |
| **除权除息** | 价格复权 + 持仓调整 | 前复权/后复权价格计算 |
| **融资融券** | 保证金计算 + 强平逻辑 | 维持担保比例监控 |
| **手续费** | 佣金(万2.5)+印花税(千1)+过户费(万0.2) | 双边/单边收费区分 |
| **隔夜成本** | 融资利息 + 融券费用 | 日终资金成本计算 |

### 2.2.2 精细化交易成本模型

```python
# backtest_engine.py

class AlmgrenChrissImpact:
    """
    Almgren-Chriss市场冲击模型
    
    模型公式:
    总成本 = 临时性冲击 + 永久性冲击
    
    临时性冲击 (Temporary Impact):
        h(X) = η * (X / (V * T))^β * σ * sqrt(T)
    
    永久性冲击 (Permanent Impact):
        g(X) = γ * (X / V) * σ * sqrt(T)
    
    其中:
    - X: 订单数量
    - V: 日均成交量
    - T: 执行时间(天)
    - σ: 日波动率
    - η, γ: 冲击系数
    - β: 形状参数(通常0.5-0.6)
    """
    def __init__(
        self,
        permanent_impact: float = 0.1,    # γ: 永久性冲击系数
        temporary_impact: float = 0.3,    # η: 临时性冲击系数
        beta: float = 0.6,                 # 形状参数
        volatility_scale: bool = True      # 是否按波动率缩放
    ):
        self.gamma = permanent_impact
        self.eta = temporary_impact
        self.beta = beta
        self.volatility_scale = volatility_scale
        
    def calculate_impact_cost(
        self,
        order_size: int,           # 订单股数
        avg_daily_volume: int,     # 日均成交量
        volatility: float,         # 日波动率(标准差)
        execution_days: int = 1    # 预计执行天数
    ) -> Dict[str, float]:
        """计算市场冲击成本"""
        
        # 参与率
        participation_rate = order_size / (avg_daily_volume * execution_days)
        
        # 永久性冲击 (价格永久偏移)
        permanent_cost = self.gamma * participation_rate
        if self.volatility_scale:
            permanent_cost *= volatility * np.sqrt(execution_days)
        
        # 临时性冲击 (执行期内暂时影响，会恢复)
        temporary_cost = self.eta * (participation_rate ** self.beta)
        if self.volatility_scale:
            temporary_cost *= volatility * np.sqrt(execution_days)
        
        # 总冲击成本
        total_cost = permanent_cost + temporary_cost
        
        return {
            'permanent_impact': permanent_cost,
            'temporary_impact': temporary_cost,
            'total_impact': total_cost,
            'participation_rate': participation_rate,
            'estimated_price_impact': total_cost  # 价格偏移百分比
        }
    
    def optimal_execution_schedule(
        self,
        total_shares: int,
        avg_daily_volume: int,
        volatility: float,
        risk_aversion: float = 1e-6,
        max_days: int = 5
    ) -> List[int]:
        """
        计算最优执行时间表
        
        使用Almgren-Chriss最优执行模型
        
        Args:
            risk_aversion: 风险厌恶系数 (越大越保守，执行越快)
            
        Returns:
            每日执行数量列表
        """
        # 简化版：等时间间隔的最优解
        shares_remaining = total_shares
        schedule = []
        
        for day in range(max_days):
            # 计算当日最优执行量
            if shares_remaining <= 0:
                break
                
            # 最优执行比例 (简化公式)
            optimal_fraction = 1 / (max_days - day)
            shares_today = int(shares_remaining * optimal_fraction)
            shares_today = min(shares_today, avg_daily_volume * 0.1)  # 不超过日成交量10%
            
            schedule.append(shares_today)
            shares_remaining -= shares_today
        
        # 处理剩余
        if shares_remaining > 0:
            schedule[-1] += shares_remaining
            
        return schedule


class DynamicSlippage:
    """
    动态滑点模型
    
    基于实时盘口深度的滑点估算
    """
    def __init__(
        self,
        mode: str = 'volume_adaptive',  # volume_adaptive / fixed / percentage
        depth_levels: int = 5,          # 盘口深度层数
        base_slippage: float = 0.001    # 基础滑点(0.1%)
    ):
        self.mode = mode
        self.depth_levels = depth_levels
        self.base_slippage = base_slippage
        
    def estimate_slippage(
        self,
        order_size: int,
        orderbook: Dict,    # {'bids': [[price, qty], ...], 'asks': [...]}
        side: str           # 'buy' or 'sell'
    ) -> float:
        """
        估算滑点
        
        基于订单簿深度计算实际成交价格与当前价的偏差
        """
        if self.mode == 'fixed':
            return self.base_slippage
        
        levels = orderbook['asks'] if side == 'buy' else orderbook['bids']
        
        # 计算需要吃掉的深度
        remaining = order_size
        total_cost = 0
        
        for level_price, level_qty in levels[:self.depth_levels]:
            if remaining <= 0:
                break
            
            fill_qty = min(remaining, level_qty)
            total_cost += fill_qty * level_price
            remaining -= fill_qty
        
        if remaining > 0:
            # 深度不足，加大滑点惩罚
            total_cost += remaining * (levels[-1][0] * 1.02 if side == 'buy' else levels[-1][0] * 0.98)
        
        # 计算平均成交价格
        avg_fill_price = total_cost / order_size
        
        # 当前最优价格
        current_price = levels[0][0]
        
        # 滑点百分比
        slippage = abs(avg_fill_price - current_price) / current_price
        
        return slippage
    
    def estimate_impact_adjusted_slippage(
        self,
        order_size: int,
        avg_daily_volume: int,
        volatility: float,
        orderbook: Dict,
        side: str
    ) -> float:
        """结合市场冲击和盘口深度的综合滑点"""
        
        # 盘口深度滑点
        book_slippage = self.estimate_slippage(order_size, orderbook, side)
        
        # 市场冲击估算 (简化版)
        participation = order_size / avg_daily_volume
        impact_slippage = 0.1 * participation * volatility * 16  # 年化波动转换
        
        # 综合 (取较大者，考虑相关性)
        total_slippage = np.sqrt(book_slippage**2 + impact_slippage**2)
        
        return min(total_slippage, 0.05)  # 滑点上限5%


class BiasDetector:
    """
    回测偏差检测器
    
    检测并修正三类主要偏差：
    1. 前视偏差 (Look-ahead Bias)
    2. 幸存者偏差 (Survivorship Bias)
    3. 过拟合 (Overfitting)
    """
    def __init__(
        self,
        check_lookahead: bool = True,
        check_survivorship: bool = True,
        check_overfit: bool = True
    ):
        self.check_lookahead = check_lookahead
        self.check_survivorship = check_survivorship
        self.check_overfit = check_overfit
        
    def detect_lookahead_bias(
        self,
        trades: pd.DataFrame,
        signal_time: str,
        execution_time: str
    ) -> Dict:
        """
        检测前视偏差
        
        检查是否在信号产生前使用了未来信息
        """
        issues = []
        
        # 检查信号时间是否早于数据可用时间
        for _, trade in trades.iterrows():
            if trade[signal_time] < trade.get('data_available_time', trade[signal_time]):
                issues.append({
                    'trade_id': trade.get('id'),
                    'issue': '使用未来数据生成信号',
                    'severity': 'critical'
                })
        
        return {
            'has_lookahead_bias': len(issues) > 0,
            'issues': issues,
            'recommendation': '确保信号只使用当前及历史数据'
        }
    
    def detect_survivorship_bias(
        self,
        universe: List[str],
        start_date: str,
        end_date: str
    ) -> Dict:
        """
        检测幸存者偏差
        
        检查是否只使用了存活股票，忽略了退市/停牌股票
        """
        from data_layer import DataLayer
        
        # 获取历史完整股票列表（包含已退市）
        historical_universe = DataLayer().get_historical_universe(
            start_date, end_date, include_delisted=True
        )
        
        # 对比
        current_only = set(universe) - set(historical_universe)
        missing_delisted = set(historical_universe) - set(universe)
        
        return {
            'has_survivorship_bias': len(missing_delisted) > 0,
            'missing_stocks': list(missing_delisted),
            'survivor_ratio': len(universe) / len(historical_universe),
            'recommendation': f'应包含{len(missing_delisted)}只已退市/停牌股票'
        }
    
    def detect_overfitting(
        self,
        is_performance: Dict,    # 样本内表现
        oos_performance: Dict,   # 样本外表现
        threshold: float = 0.3   # 衰减阈值
    ) -> Dict:
        """
        检测过拟合
        
        比较样本内外表现差异
        """
        metrics = ['sharpe', 'annual_return', 'calmar_ratio']
        degradation = {}
        
        for metric in metrics:
            is_val = is_performance.get(metric, 0)
            oos_val = oos_performance.get(metric, 0)
            
            if is_val != 0:
                degradation[metric] = (is_val - oos_val) / abs(is_val)
            else:
                degradation[metric] = 0
        
        avg_degradation = np.mean(list(degradation.values()))
        
        return {
            'is_overfitted': avg_degradation > threshold,
            'degradation': degradation,
            'avg_degradation': avg_degradation,
            'recommendation': '增加样本外验证周期，或使用正则化'
        }


class ProfessionalBacktester:
    """
    专业级回测引擎
    
    核心特性：
    1. A股全规则精准模拟
    2. Almgren-Chriss市场冲击模型
    3. 动态滑点估算
    4. 三类偏差检测
    5. Walk Forward Analysis
    """
    def __init__(self):
        # 交易成本模型
        self.impact_model = AlmgrenChrissImpact(
            permanent_impact=0.1,
            temporary_impact=0.3,
            volatility_scale=True
        )
        
        # 滑点模型
        self.slippage = DynamicSlippage(
            mode='volume_adaptive',
            depth_levels=5
        )
        
        # 偏差检测
        self.bias_detector = BiasDetector(
            check_lookahead=True,
            check_survivorship=True,
            check_overfit=True
        )
        
        # A股规则引擎
        self.rules_engine = AStockRulesEngine()
        
        # 费用计算器
        self.fee_calculator = FeeCalculator()
        
    def run_backtest(
        self,
        strategy,
        data: pd.DataFrame,
        start_date: str,
        end_date: str,
        initial_capital: float = 10000000,
        apply_impact: bool = True,
        apply_slippage: bool = True
    ) -> BacktestResult:
        """
        执行单周期回测
        
        Args:
            strategy: 策略对象 (必须有 generate_signals 和 on_bar 方法)
            data: 市场数据 DataFrame
            initial_capital: 初始资金(默认1000万)
            
        Returns:
            BacktestResult: 回测结果对象
        """
        portfolio = Portfolio(initial_capital)
        
        for timestamp, bar in data.iterrows():
            # 1. 生成信号
            signals = strategy.generate_signals(bar, portfolio)
            
            # 2. 检查A股规则约束
            valid_signals = self.rules_engine.validate_signals(
                signals, portfolio, bar
            )
            
            # 3. 计算交易成本
            for signal in valid_signals:
                # 市场冲击
                if apply_impact:
                    impact = self.impact_model.calculate_impact_cost(
                        signal['quantity'],
                        bar['avg_volume'],
                        bar['volatility']
                    )
                    signal['impact_cost'] = impact['total_impact']
                
                # 滑点
                if apply_slippage:
                    slip = self.slippage.estimate_slippage(
                        signal['quantity'],
                        bar['orderbook'],
                        signal['side']
                    )
                    signal['slippage'] = slip
                
                # 手续费
                fees = self.fee_calculator.calculate(
                    signal['quantity'],
                    signal['price'],
                    signal['side']
                )
                signal['fees'] = fees
            
            # 4. 执行交易
            for signal in valid_signals:
                portfolio.execute(signal)
            
            # 5. 日终结算
            portfolio.daily_settlement(bar)
        
        # 生成回测报告
        return BacktestResult(portfolio, self)
    
    def run_wfa(
        self,
        strategy,
        data: pd.DataFrame,
        train_window: int = 252,    # 训练窗口(交易日)
        test_window: int = 63,       # 测试窗口(交易日)
        step_size: int = 63          # 滚动步长
    ) -> WFAReport:
        """
        Walk Forward Analysis 滚动回测
        
        核心优势：
        1. 避免过拟合：每次都在新数据上测试
        2. 模拟真实交易：定期重新优化参数
        3. 更可靠的绩效评估
        
        Args:
            train_window: 训练期长度(默认252日=1年)
            test_window: 测试期长度(默认63日=1季度)
            step_size: 窗口滚动步长
        """
        results = []
        strategy_params_history = []
        
        # 生成滚动窗口
        windows = self._generate_rolling_windows(
            data, train_window, test_window, step_size
        )
        
        for i, (train_data, test_data) in enumerate(windows):
            print(f"WFA Window {i+1}/{len(windows)}")
            
            # 1. 训练期：策略参数优化
            strategy_clone = strategy.clone()
            best_params = strategy_clone.fit(
                train_data,
                objective='sharpe_ratio'
            )
            strategy_params_history.append({
                'window': i,
                'params': best_params,
                'train_sharpe': strategy_clone.train_performance['sharpe']
            })
            
            # 2. 测试期：样本外评估
            perf = strategy_clone.evaluate(
                test_data,
                impact_model=self.impact_model if i > 0 else None,
                slippage=self.slippage if i > 0 else None
            )
            results.append({
                'window': i,
                'train_start': train_data.index[0],
                'train_end': train_data.index[-1],
                'test_start': test_data.index[0],
                'test_end': test_data.index[-1],
                'train_sharpe': strategy_clone.train_performance['sharpe'],
                'test_sharpe': perf['sharpe'],
                'test_return': perf['annual_return'],
                'test_maxdd': perf['max_drawdown']
            })
        
        # 3. 偏差检测
        is_perfs = [r['train_sharpe'] for r in results]
        oos_perfs = [r['test_sharpe'] for r in results]
        
        overfit_check = self.bias_detector.detect_overfitting(
            {'sharpe': np.mean(is_perfs)},
            {'sharpe': np.mean(oos_perfs)}
        )
        
        return WFAReport(results, strategy_params_history, overfit_check)
    
    def _generate_rolling_windows(
        self,
        data: pd.DataFrame,
        train_window: int,
        test_window: int,
        step_size: int
    ) -> List[Tuple[pd.DataFrame, pd.DataFrame]]:
        """生成滚动窗口"""
        windows = []
        n_samples = len(data)
        
        start_idx = 0
        while start_idx + train_window + test_window <= n_samples:
            train_start = start_idx
            train_end = start_idx + train_window
            test_start = train_end
            test_end = train_end + test_window
            
            train_data = data.iloc[train_start:train_end]
            test_data = data.iloc[test_start:test_end]
            
            windows.append((train_data, test_data))
            start_idx += step_size
        
        return windows


class WFAReport:
    """WFA报告"""
    def __init__(self, results, params_history, overfit_check):
        self.results = pd.DataFrame(results)
        self.params_history = params_history
        self.overfit_check = overfit_check
        
    def summary(self) -> Dict:
        """汇总报告"""
        return {
            'n_windows': len(self.results),
            'avg_train_sharpe': self.results['train_sharpe'].mean(),
            'avg_test_sharpe': self.results['test_sharpe'].mean(),
            'sharpe_degradation': (
                self.results['train_sharpe'].mean() - 
                self.results['test_sharpe'].mean()
            ),
            'consistency_ratio': (
                self.results['test_sharpe'] > 0
            ).mean(),  # 测试期盈利窗口比例
            'overfit_warning': self.overfit_check['is_overfitted'],
            'recommendation': self.overfit_check['recommendation']
        }
    
    def plot_rolling_performance(self):
        """绘制滚动窗口绩效图"""
        import matplotlib.pyplot as plt
        
        fig, axes = plt.subplots(2, 1, figsize=(12, 8))
        
        # 夏普比率对比
        axes[0].plot(self.results['window'], self.results['train_sharpe'], 
                    label='Train Sharpe', marker='o')
        axes[0].plot(self.results['window'], self.results['test_sharpe'], 
                    label='Test Sharpe', marker='s')
        axes[0].axhline(y=0, color='r', linestyle='--', alpha=0.5)
        axes[0].set_ylabel('Sharpe Ratio')
        axes[0].legend()
        axes[0].set_title('Walk Forward Analysis: Train vs Test Performance')
        
        # 收益与回撤
        ax2 = axes[1]
        ax2.bar(self.results['window'], self.results['test_return'], 
               alpha=0.7, label='Annual Return')
        ax2.set_ylabel('Annual Return')
        ax2_twin = ax2.twinx()
        ax2_twin.plot(self.results['window'], self.results['test_maxdd'], 
                     color='r', marker='x', label='Max Drawdown')
        ax2_twin.set_ylabel('Max Drawdown', color='r')
        ax2_twin.tick_params(axis='y', labelcolor='r')
        
        plt.tight_layout()
        return fig


class AStockRulesEngine:
    """A股规则引擎"""
    
    def __init__(self):
        self.price_limits = {
            '主板': 0.10,
            '科创板': 0.20,
            '创业板': 0.20,
            'ST': 0.05
        }
        
    def validate_signals(
        self,
        signals: List[Dict],
        portfolio: 'Portfolio',
        bar: pd.Series
    ) -> List[Dict]:
        """验证信号是否符合A股规则"""
        valid = []
        
        for signal in signals:
            code = signal['code']
            side = signal['side']
            qty = signal['quantity']
            price = signal['price']
            
            # 1. T+1检查 (卖出时检查持仓)
            if side == 'sell':
                sellable = portfolio.get_sellable_shares(code)
                if qty > sellable:
                    signal['quantity'] = sellable
                    signal['warnings'].append(f'T+1限制：仅可卖{sellable}股')
            
            # 2. 涨跌停检查
            price_limit = self._get_price_limit(code, bar)
            if side == 'buy' and price > bar['close'] * (1 + price_limit):
                signal['warnings'].append('买入价超过涨停价')
                continue
            if side == 'sell' and price < bar['close'] * (1 - price_limit):
                signal['warnings'].append('卖出价低于跌停价')
                continue
            
            # 3. 停牌检查
            if bar.get('is_suspended', False):
                signal['warnings'].append('股票停牌')
                continue
            
            # 4. 最小交易单位
            if qty % 100 != 0:
                signal['quantity'] = (qty // 100) * 100
                signal['warnings'].append('调整为100股整数倍')
            
            if signal['quantity'] > 0:
                valid.append(signal)
        
        return valid
    
    def _get_price_limit(self, code: str, bar: pd.Series) -> float:
        """获取股票涨跌幅限制"""
        if code.startswith('ST'):
            return self.price_limits['ST']
        elif code.startswith('688'):  # 科创板
            return self.price_limits['科创板']
        elif code.startswith('300'):  # 创业板
            return self.price_limits['创业板']
        else:
            return self.price_limits['主板']


class FeeCalculator:
    """A股费用计算器"""
    
    def __init__(self):
        # 默认费率
        self.commission_rate = 0.00025    # 佣金：万2.5
        self.min_commission = 5           # 最低佣金5元
        self.stamp_duty_rate = 0.001      # 印花税：千1 (仅卖出)
        self.transfer_fee_rate = 0.00002  # 过户费：万0.2 (双边)
        
    def calculate(
        self,
        quantity: int,
        price: float,
        side: str
    ) -> Dict[str, float]:
        """计算交易费用"""
        amount = quantity * price
        
        # 佣金 (双边)
        commission = max(amount * self.commission_rate, self.min_commission)
        
        # 印花税 (仅卖出)
        stamp_duty = amount * self.stamp_duty_rate if side == 'sell' else 0
        
        # 过户费 (双边)
        transfer_fee = amount * self.transfer_fee_rate
        
        total_fee = commission + stamp_duty + transfer_fee
        
        return {
            'commission': commission,
            'stamp_duty': stamp_duty,
            'transfer_fee': transfer_fee,
            'total_fee': total_fee,
            'fee_ratio': total_fee / amount if amount > 0 else 0
        }
```

---

*Module: Professional Backtest Engine*  
*Sub-module: 2.2.1 - 2.2.2*  
*Status: 详细设计记录*
