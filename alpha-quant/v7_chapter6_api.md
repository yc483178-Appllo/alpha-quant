# Alpha-Genesis V7.0 - 第六章：新增API端点汇总

## 6.1 API端点总览

V7.0新增18个核心API端点，覆盖因子研发、回测、归因、执行、仿真、合规、GNN、场景生成、Meta-RL、进化算法、HMM等全模块。

---

## 6.2 因子研发模块 API

### POST /api/v7/factors/mine
**触发因子挖掘任务**

**请求体：**
```json
{
  "universe": ["000001.SZ", "000002.SZ", "600519.SH"],
  "n_factors": 50,
  "gp_config": {
    "population": 500,
    "generations": 100,
    "operators": ["add", "sub", "mul", "div", "rank", "ts_mean", "ts_std"]
  },
  "automl_config": {
    "n_trials": 1000,
    "timeout": 3600
  },
  "enable_causal": true,
  "enable_gnn_interaction": true
}
```

**响应：**
```json
{
  "task_id": "FM_20250310_001",
  "status": "started",
  "estimated_completion": "2025-03-10T16:00:00Z",
  "message": "Factor mining task started with GP+Optuna+Causal validation"
}
```

---

### GET /api/v7/factors/library
**获取因子库列表+IC/IR**

**查询参数：**
- `category`: 因子分类 (alpha/risk/all)
- `sort_by`: 排序字段 (ic_mean/ic_ir/sharpe)
- `min_ic`: 最小IC阈值
- `page`: 页码
- `page_size`: 每页数量

**响应：**
```json
{
  "total": 150,
  "page": 1,
  "page_size": 20,
  "factors": [
    {
      "id": "FACTOR_001",
      "name": "Momentum_20D",
      "category": "alpha",
      "ic_mean": 0.045,
      "ic_ir": 0.52,
      "sharpe": 1.23,
      "turnover": 0.35,
      "causal_validated": true,
      "causal_strength": 0.78,
      "gnn_interaction_score": 0.65
    }
  ]
}
```

---

### GET /api/v7/factors/{id}/causal
**因果推断检验结果**

**路径参数：**
- `id`: 因子ID

**响应：**
```json
{
  "factor_id": "FACTOR_001",
  "factor_name": "Momentum_20D",
  "causal_effect": 0.045,
  "confidence_interval": [0.032, 0.058],
  "p_value": 0.002,
  "refutation_tests": [
    {
      "method": "random_common_cause",
      "passed": true,
      "p_value": 0.45
    },
    {
      "method": "placebo_treatment",
      "passed": true,
      "p_value": 0.38
    }
  ],
  "causal_graph": "digraph {...}",
  "validation_status": "passed",
  "recommendation": "Include in production"
}
```

---

## 6.3 回测模块 API

### POST /api/v7/backtest/wfa
**启动WFA滚动回测**

**请求体：**
```json
{
  "strategy_id": "STR_001",
  "strategy_code": "...",
  "data": {
    "start_date": "2018-01-01",
    "end_date": "2024-12-31",
    "universe": "hs300"
  },
  "wfa_config": {
    "train_window": 252,
    "test_window": 63,
    "step_size": 63
  },
  "cost_model": {
    "commission": 0.00025,
    "slippage": "almgren_chriss",
    "impact_model": true
  }
}
```

**响应：**
```json
{
  "task_id": "WFA_20250310_001",
  "status": "running",
  "n_windows": 38,
  "current_window": 0,
  "progress_percent": 0,
  "estimated_completion": "2025-03-10T14:30:00Z"
}
```

---

### POST /api/v7/backtest/bias-check
**偏差检测（前视/幸存者/过拟合）**

**请求体：**
```json
{
  "backtest_results": {
    "trades": [...],
    "daily_returns": [...],
    "positions": [...]
  },
  "checks": [
    "lookahead_bias",
    "survivorship_bias",
    "overfitting"
  ]
}
```

**响应：**
```json
{
  "overall_passed": false,
  "checks": {
    "lookahead_bias": {
      "passed": true,
      "issues": []
    },
    "survivorship_bias": {
      "passed": false,
      "issues": [
        {
          "type": "missing_delisted_stocks",
          "severity": "high",
          "description": "Missing 15 delisted stocks from universe",
          "affected_periods": ["2020-03", "2021-09"]
        }
      ]
    },
    "overfitting": {
      "passed": false,
      "is_sample_sharpe": 1.85,
      "oos_sample_sharpe": 1.12,
      "degradation": 0.39,
      "severity": "medium"
    }
  },
  "recommendations": [
    "Include delisted stocks in backtest universe",
    "Reduce strategy complexity to prevent overfitting"
  ]
}
```

---

## 6.4 绩效归因模块 API

### GET /api/v7/attribution/brinson
**获取Brinson归因结果**

**查询参数：**
- `portfolio_id`: 组合ID
- `start_date`: 开始日期
- `end_date`: 结束日期
- `benchmark`: 基准指数 (如 "000300.SH")

**响应：**
```json
{
  "period": "2024-01-01 to 2024-12-31",
  "total_return": 0.152,
  "benchmark_return": 0.089,
  "excess_return": 0.063,
  "attribution": {
    "allocation_effect": 0.021,
    "selection_effect": 0.035,
    "interaction_effect": 0.007
  },
  "sector_breakdown": [
    {
      "sector": "科技",
      "portfolio_weight": 0.25,
      "benchmark_weight": 0.18,
      "portfolio_return": 0.28,
      "benchmark_return": 0.22,
      "allocation_effect": 0.008,
      "selection_effect": 0.012
    }
  ],
  "currency": "CNY"
}
```

---

### GET /api/v7/attribution/barra
**获取Barra风格归因**

**查询参数：**
- `portfolio_id`: 组合ID
- `date`: 日期 (YYYY-MM-DD)

**响应：**
```json
{
  "date": "2025-03-10",
  "portfolio_exposure": {
    "Beta": 0.85,
    "Momentum": 0.45,
    "Size": -0.23,
    "EarningsYield": 0.67,
    "ResidualVolatility": -0.12,
    "Growth": 0.34,
    "BookToPrice": 0.56,
    "Leverage": -0.08,
    "Liquidity": -0.45,
    "NonLinearSize": 0.12
  },
  "style_contribution": {
    "Beta": 0.012,
    "Momentum": 0.008,
    "Size": -0.005,
    "EarningsYield": 0.015
  },
  "industry_contribution": {
    "银行": 0.003,
    "医药": 0.007,
    "电子": 0.012
  },
  "alpha": 0.025,
  "r_squared": 0.78
}
```

---

## 6.5 执行算法模块 API

### POST /api/v7/execution/submit
**提交智能执行订单(TWAP/VWAP/冰山单)**

**请求体：**
```json
{
  "parent_order": {
    "code": "600519.SH",
    "side": "buy",
    "total_quantity": 10000,
    "price_limit": 1800.00
  },
  "algorithm": "adaptive_twap",
  "algo_params": {
    "start_time": "2025-03-10T09:30:00+08:00",
    "end_time": "2025-03-10T15:00:00+08:00",
    "urgency": 0.5,
    "min_slice_size": 100,
    "max_participation_rate": 0.1
  },
  "risk_checks": true
}
```

**响应：**
```json
{
  "parent_order_id": "ORD_20250310_001",
  "status": "submitted",
  "algorithm": "adaptive_twap",
  "n_child_orders": 20,
  "estimated_completion": "2025-03-10T15:00:00+08:00",
  "child_orders": [
    {
      "child_id": "ORD_20250310_001_C01",
      "quantity": 500,
      "trigger_time": "2025-03-10T09:30:00+08:00",
      "order_type": "limit"
    }
  ]
}
```

---

### GET /api/v7/execution/performance
**执行绩效分析**

**查询参数：**
- `order_id`: 订单ID
- `date`: 日期

**响应：**
```json
{
  "order_id": "ORD_20250310_001",
  "algorithm": "adaptive_twap",
  "status": "completed",
  "execution_summary": {
    "total_quantity": 10000,
    "filled_quantity": 10000,
    "fill_rate": 1.0,
    "avg_fill_price": 1798.50,
    "vwap": 1798.45,
    "arrival_price": 1800.00
  },
  "cost_analysis": {
    "implementation_shortfall_bps": 8.3,
    "slippage_bps": 3.2,
    "market_impact_bps": 4.1,
    "commission_bps": 1.0
  },
  "timing": {
    "submit_time": "09:30:00",
    "first_fill_time": "09:31:15",
    "completion_time": "14:52:38",
    "duration_seconds": 16958
  },
  "quality_score": 92
}
```

---

## 6.6 仿真交易模块 API

### GET /api/v7/paper-trading/status
**仿真交易状态**

**查询参数：**
- `strategy_id`: 策略ID (可选)
- `account_id`: 账户ID (可选)

**响应：**
```json
{
  "accounts": [
    {
      "account_id": "SIM_001",
      "strategy_id": "STR_001",
      "strategy_name": "Momentum_V2",
      "status": "canary_10",
      "capital": {
        "initial": 10000000,
        "current": 10850000,
        "allocated": 1000000
      },
      "performance": {
        "total_return": 0.085,
        "sharpe": 1.45,
        "max_drawdown": 0.08,
        "volatility": 0.15
      },
      "simulation_days": 45,
      "canary_stage": {
        "current": "10%",
        "next": "30%",
        "progress_percent": 100,
        "bayesian_confidence": 0.96,
        "auto_promote": true
      }
    }
  ]
}
```

---

### POST /api/v7/paper-trading/promote
**灰度升级策略**

**请求体：**
```json
{
  "account_id": "SIM_001",
  "target_stage": "canary_30",
  "method": "auto",
  "validation": {
    "min_simulation_days": 30,
    "min_sharpe": 1.2,
    "max_drawdown": 0.15,
    "bayesian_confidence": 0.95
  }
}
```

**响应：**
```json
{
  "promotion_id": "PROM_20250310_001",
  "account_id": "SIM_001",
  "from_stage": "canary_10",
  "to_stage": "canary_30",
  "status": "approved",
  "validation_results": {
    "simulation_days_passed": true,
    "sharpe_passed": true,
    "drawdown_passed": true,
    "confidence_passed": true
  },
  "effective_time": "2025-03-11T09:30:00+08:00",
  "new_capital_allocation": 3000000
}
```

---

## 6.7 合规审计模块 API

### GET /api/v7/compliance/audit-log
**审计日志查询**

**查询参数：**
- `start_time`: 开始时间
- `end_time`: 结束时间
- `event_type`: 事件类型
- `order_id`: 订单ID
- `strategy_id`: 策略ID

**响应：**
```json
{
  "total": 1523,
  "logs": [
    {
      "event_id": "AUD_001",
      "timestamp": "2025-03-10T14:32:15Z",
      "event_type": "order_sent",
      "stage": "execution",
      "order_id": "ORD_001",
      "strategy_id": "STR_001",
      "data_hash": "a1b2c3d4...",
      "signature": "e5f6g7h8...",
      "raw_data": {...}
    }
  ],
  "integrity_check": {
    "total_events": 1523,
    "violations_found": 0,
    "is_valid": true
  }
}
```

---

### GET /api/v7/compliance/alerts
**异常交易告警**

**查询参数：**
- `severity`: 严重级别 (high/medium/low)
- `status`: 状态 (active/resolved)
- `limit`: 返回数量

**响应：**
```json
{
  "total_active": 3,
  "alerts": [
    {
      "alert_id": "ALT_001",
      "timestamp": "2025-03-10T14:45:00Z",
      "type": "excessive_cancellation",
      "severity": "medium",
      "account_id": "ACC_001",
      "description": "Cancel/Fill ratio 6.5 exceeds threshold 5.0",
      "details": {
        "cancel_count": 65,
        "fill_count": 10,
        "ratio": 6.5
      },
      "status": "active",
      "auto_action": "warn"
    },
    {
      "alert_id": "ALT_002",
      "timestamp": "2025-03-10T15:10:00Z",
      "type": "potential_self_trade",
      "severity": "high",
      "description": "Potential self-trading detected between Account A and B",
      "status": "active",
      "auto_action": "block_pending"
    }
  ]
}
```

---

## 6.8 GNN模块 API

### POST /api/v7/gnn/contagion
**股票传导效应预测**

**请求体：**
```json
{
  "shock_stock": "300750.SZ",
  "shock_magnitude": -0.08,
  "affected_universe": ["002594.SZ", "603659.SH", "300073.SZ", "600519.SH"],
  "graph_types": ["supply_chain", "industry", "capital_flow"]
}
```

**响应：**
```json
{
  "shock_stock": "300750.SZ",
  "shock_magnitude": -0.08,
  "propagation_results": {
    "002594.SZ": {
      "predicted_impact": -0.052,
      "confidence": 0.87,
      "path": ["300750.SZ" -> "002594.SZ"],
      "relationship": "downstream_customer"
    },
    "603659.SH": {
      "predicted_impact": -0.048,
      "confidence": 0.82,
      "path": ["300750.SZ" -> "603659.SH"],
      "relationship": "upstream_supplier"
    },
    "300073.SZ": {
      "predicted_impact": -0.035,
      "confidence": 0.75,
      "path": ["300750.SZ" -> "300073.SZ"],
      "relationship": "industry_peer"
    },
    "600519.SH": {
      "predicted_impact": -0.005,
      "confidence": 0.45,
      "path": [],
      "relationship": "none"
    }
  },
  "risk_assessment": {
    "high_impact_stocks": ["002594.SZ", "603659.SH"],
    "recommended_action": "reduce_exposure",
    "estimated_portfolio_impact": -0.023
  }
}
```

---

## 6.9 场景生成模块 API

### POST /api/v7/scenario/generate
**生成极端场景**

**请求体：**
```json
{
  "scenario_name": "三重重压",
  "components": ["trade_war", "property_crisis", "pandemic"],
  "intensities": {
    "trade_war": 0.9,
    "property_crisis": 1.0,
    "pandemic": 0.7
  },
  "conditions": {
    "max_drawdown": 0.35,
    "duration_days": 60,
    "volatility": 0.05
  },
  "n_scenarios": 100,
  "market_rules": {
    "price_limit": 0.1,
    "t_plus_1": true
  }
}
```

**响应：**
```json
{
  "generation_id": "GEN_20250310_001",
  "status": "completed",
  "n_scenarios_generated": 100,
  "scenarios": [
    {
      "scenario_id": "S_001",
      "max_drawdown": 0.328,
      "final_return": -0.25,
      "volatility": 0.048,
      "duration_days": 58,
      "data_url": "/scenarios/GEN_20250310_001/S_001.csv"
    }
  ],
  "summary_statistics": {
    "avg_max_drawdown": 0.312,
    "avg_final_return": -0.23,
    "survival_rate": 0.65
  }
}
```

---

## 6.10 Meta-RL模块 API

### POST /api/v7/meta-rl/adapt
**触发Meta-RL快速适应**

**请求体：**
```json
{
  "current_regime": "volatile_bear",
  "previous_regime": "sideways",
  "recent_data": [
    {"state": [...], "action": 5, "reward": 0.012},
    {"state": [...], "action": 3, "reward": -0.008},
    ...
  ],
  "adaptation_config": {
    "n_gradient_steps": 5,
    "learning_rate": 0.001,
    "batch_size": 32
  }
}
```

**响应：**
```json
{
  "adaptation_id": "ADAPT_20250310_001",
  "status": "completed",
  "from_regime": "sideways",
  "to_regime": "volatile_bear",
  "adaptation_time_seconds": 8.5,
  "performance": {
    "initial_loss": 2.45,
    "final_loss": 1.82,
    "loss_reduction": 0.63,
    "improvement_percent": 25.7
  },
  "n_gradient_steps": 5,
  "model_checkpoint_url": "/models/adapted/ADAPT_20250310_001.pth"
}
```

---

## 6.11 进化算法模块 API

### GET /api/v7/evolution/nsga3
**获取NSGA-III多目标Pareto前沿**

**查询参数：**
- `generation`: 代数 (可选，默认最新)
- `objectives`: 目标维度 (如 "sharpe,return,drawdown")

**响应：**
```json
{
  "generation": 45,
  "pareto_front_size": 23,
  "objectives": ["sharpe", "return", "drawdown", "turnover"],
  "solutions": [
    {
      "strategy_id": "STR_045_001",
      "genes": [0.5, -0.3, 0.8, ...],
      "objectives": {
        "sharpe": 1.85,
        "return": 0.25,
        "drawdown": -0.12,
        "turnover": 0.35
      },
      "rank": 1,
      "crowding_distance": 0.85,
      "dominates": ["STR_045_003", "STR_045_007"]
    }
  ],
  "hypervolume": 0.72,
  "diversity": 0.68
}
```

---

## 6.12 HMM模块 API

### GET /api/v7/hmm/realtime
**实时多尺度政权状态**

**查询参数：**
- `scales`: 时间尺度 (daily,hourly,minute，逗号分隔)
- `features`: 特征列表

**响应：**
```json
{
  "timestamp": "2025-03-10T15:30:00+08:00",
  "current_regime": 3,
  "regime_name": "high_volatility_bear",
  "confidence": 0.78,
  "is_transition": false,
  "probabilities": [0.05, 0.08, 0.09, 0.78, 0.0, 0.0],
  "scale_predictions": {
    "daily": {
      "state": 3,
      "confidence": 0.82,
      "log_likelihood": -125.3
    },
    "hourly": {
      "state": 3,
      "confidence": 0.75,
      "log_likelihood": -89.2
    },
    "minute": {
      "state": 2,
      "confidence": 0.65,
      "log_likelihood": -56.8
    }
  },
  "fused_confidence": 0.78,
  "transition_smoothness": 0.85,
  "recommended_strategy": "defensive",
  "recommended_leverage": 0.5
}
```

---

## 6.13 API汇总表

| 模块 | API端点 | 方法 | 功能 |
|------|---------|------|------|
| 因子 | /api/v7/factors/mine | POST | 触发因子挖掘任务 |
| 因子 | /api/v7/factors/library | GET | 获取因子库+IC/IR |
| 因子 | /api/v7/factors/{id}/causal | GET | 因果推断检验结果 |
| 回测 | /api/v7/backtest/wfa | POST | 启动WFA滚动回测 |
| 回测 | /api/v7/backtest/bias-check | POST | 偏差检测 |
| 归因 | /api/v7/attribution/brinson | GET | Brinson归因结果 |
| 归因 | /api/v7/attribution/barra | GET | Barra风格归因 |
| 执行 | /api/v7/execution/submit | POST | 提交智能执行订单 |
| 执行 | /api/v7/execution/performance | GET | 执行绩效分析 |
| 仿真 | /api/v7/paper-trading/status | GET | 仿真交易状态 |
| 仿真 | /api/v7/paper-trading/promote | POST | 灰度升级策略 |
| 合规 | /api/v7/compliance/audit-log | GET | 审计日志查询 |
| 合规 | /api/v7/compliance/alerts | GET | 异常交易告警 |
| GNN | /api/v7/gnn/contagion | POST | 股票传导效应预测 |
| 场景 | /api/v7/scenario/generate | POST | 生成极端场景 |
| Meta-RL | /api/v7/meta-rl/adapt | POST | 触发Meta-RL快速适应 |
| 进化 | /api/v7/evolution/nsga3 | GET | 获取NSGA-III Pareto前沿 |
| HMM | /api/v7/hmm/realtime | GET | 实时多尺度政权状态 |
| **总计** | | | **18个API端点** |

---

*Module: Chapter 6 - API Endpoints Summary*  
*Status: 详细设计记录*
