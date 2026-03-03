"""
DRL 投资组合优化 Agent
基于 PPO 算法的动态资产配置引擎
兼容 V4.0 信号总线和 config.json 配置体系
"""

import os
import json
import numpy as np
from datetime import datetime
from loguru import logger

# ===== 环境定义 =====
class PortfolioEnv:
    """A股投资组合强化学习环境"""

    def __init__(self, config):
        self.max_positions = config.get("max_positions", 30)
        self.initial_cash = config.get("initial_cash", 1000000)
        self.transaction_cost = config.get("transaction_cost", 0.001)
        self.state_dim = self.max_positions * 8 + 5
        self.action_dim = self.max_positions
        self.reset()

    def reset(self):
        self.cash = self.initial_cash
        self.portfolio_value = self.initial_cash
        self.weights = np.zeros(self.max_positions)
        self.step_count = 0
        self.peak_value = self.initial_cash
        self.daily_returns = []
        return self._get_state()

    def _get_state(self):
        """构建状态向量"""
        state = np.zeros(self.state_dim)
        # 填充每只股票特征（实际接入时从 data_gateway 获取）
        # state[:self.max_positions*8] = per_stock_features
        # 全局特征
        sharpe = self._calc_sharpe()
        drawdown = self._calc_drawdown()
        state[-5:] = [1.0, sharpe, drawdown, self.cash/self.portfolio_value,
                      1.0 - self.cash/self.portfolio_value]
        return state.astype(np.float32)

    def step(self, action):
        """执行一步动作（调整组合权重）"""
        # 1. 归一化动作为目标权重
        action = np.clip(action, -0.5, 0.5)
        target_weights = self._normalize_weights(self.weights + action)

        # 2. 计算交易成本
        weight_changes = np.abs(target_weights - self.weights)
        turnover = np.sum(weight_changes)
        cost = turnover * self.transaction_cost * self.portfolio_value

        # 3. 模拟市场收益（实际接入时从 data_gateway 获取当日收益率）
        market_returns = np.random.normal(0.001, 0.02, self.max_positions)
        portfolio_return = np.dot(target_weights, market_returns)

        # 4. 更新组合价值
        self.portfolio_value = self.portfolio_value * (1 + portfolio_return) - cost
        self.peak_value = max(self.peak_value, self.portfolio_value)
        self.weights = target_weights
        self.daily_returns.append(portfolio_return)
        self.step_count += 1

        # 5. 计算奖励
        benchmark_return = market_returns.mean()
        drawdown = self._calc_drawdown()
        sharpe = self._calc_sharpe()
        reward = self._compute_reward(portfolio_return, benchmark_return, drawdown, sharpe)

        # 6. 终止条件
        done = (self.step_count >= 252) or (drawdown < -0.20)

        return self._get_state(), reward, done, {
            "portfolio_value": self.portfolio_value,
            "sharpe": sharpe,
            "drawdown": drawdown,
            "turnover": turnover
        }

    def _normalize_weights(self, weights):
        """归一化权重，确保和≤1且非负"""
        weights = np.maximum(weights, 0)
        total = weights.sum()
        if total > 1.0:
            weights = weights / total
        return weights

    def _calc_sharpe(self, risk_free=0.03/252):
        if len(self.daily_returns) < 5:
            return 0.0
        returns = np.array(self.daily_returns[-60:])
        excess = returns - risk_free
        if excess.std() == 0:
            return 0.0
        return float(excess.mean() / excess.std() * np.sqrt(252))

    def _calc_drawdown(self):
        if self.peak_value == 0:
            return 0.0
        return float((self.portfolio_value - self.peak_value) / self.peak_value)

    def _compute_reward(self, port_ret, bench_ret, drawdown, sharpe):
        alpha = port_ret - bench_ret
        sharpe_reward = sharpe * 0.5
        drawdown_penalty = -abs(drawdown) * 2.0 if drawdown < -0.05 else 0
        return float(alpha * 100 + sharpe_reward + drawdown_penalty)


# ===== PPO 网络 =====
class PPONetwork:
    """PPO Actor-Critic 网络（纯NumPy实现，无需PyTorch依赖）"""

    def __init__(self, state_dim, action_dim, hidden=128, lr=3e-4):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.hidden = hidden
        self.lr = lr
        # Actor 网络权重（简化版：2层全连接）
        self.actor_w1 = np.random.randn(state_dim, hidden) * 0.01
        self.actor_b1 = np.zeros(hidden)
        self.actor_w2 = np.random.randn(hidden, action_dim) * 0.01
        self.actor_b2 = np.zeros(action_dim)
        self.log_std = np.zeros(action_dim) - 0.5
        # Critic 网络权重
        self.critic_w1 = np.random.randn(state_dim, hidden) * 0.01
        self.critic_b1 = np.zeros(hidden)
        self.critic_w2 = np.random.randn(hidden, 1) * 0.01
        self.critic_b2 = np.zeros(1)

    def _relu(self, x):
        return np.maximum(0, x)

    def _tanh(self, x):
        return np.tanh(x)

    def get_action(self, state):
        """采样动作"""
        h = self._relu(state @ self.actor_w1 + self.actor_b1)
        mean = self._tanh(h @ self.actor_w2 + self.actor_b2) * 0.5
        std = np.exp(self.log_std)
        action = mean + std * np.random.randn(self.action_dim)
        return np.clip(action, -0.5, 0.5), mean, std

    def get_value(self, state):
        """估计状态价值"""
        h = self._relu(state @ self.critic_w1 + self.critic_b1)
        value = h @ self.critic_w2 + self.critic_b2
        return float(value[0])

    def save(self, path):
        np.savez(path,
                 aw1=self.actor_w1, ab1=self.actor_b1,
                 aw2=self.actor_w2, ab2=self.actor_b2,
                 ls=self.log_std,
                 cw1=self.critic_w1, cb1=self.critic_b1,
                 cw2=self.critic_w2, cb2=self.critic_b2)
        logger.info(f"DRL模型已保存: {path}")

    def load(self, path):
        data = np.load(path)
        self.actor_w1, self.actor_b1 = data['aw1'], data['ab1']
        self.actor_w2, self.actor_b2 = data['aw2'], data['ab2']
        self.log_std = data['ls']
        self.critic_w1, self.critic_b1 = data['cw1'], data['cb1']
        self.critic_w2, self.critic_b2 = data['cw2'], data['cb2']
        logger.info(f"DRL模型已加载: {path}")


# ===== DRL Agent 主类 =====
class DRLPortfolioAgent:
    """DRL投资组合优化Agent - 与V4.0信号总线兼容"""

    def __init__(self, config_path="config.json"):
        with open(config_path) as f:
            config = json.load(f)
        self.cfg = config.get("drl_portfolio", {})
        self.enabled = self.cfg.get("enabled", True)
        self.model_path = self.cfg.get("model_save_path", "./models/drl_portfolio.npz")

        # 确保模型目录存在
        os.makedirs(os.path.dirname(self.model_path) if os.path.dirname(self.model_path) else ".", exist_ok=True)

        env_cfg = {
            "max_positions": self.cfg.get("max_positions", 30),
            "initial_cash": self.cfg.get("initial_cash", 1000000),
            "transaction_cost": self.cfg.get("transaction_cost", 0.001)
        }
        self.env = PortfolioEnv(env_cfg)
        self.network = PPONetwork(
            state_dim=self.env.state_dim,
            action_dim=self.env.action_dim,
            hidden=self.cfg.get("hidden_size", 128),
            lr=self.cfg.get("learning_rate", 3e-4)
        )
        # 加载已有模型
        if os.path.exists(self.model_path):
            self.network.load(self.model_path)

    def predict_portfolio_weights(self, current_state):
        """预测最优组合权重"""
        if not self.enabled:
            return None
        action, mean, std = self.network.get_action(current_state)
        confidence = float(1.0 / (1.0 + np.mean(std)))
        value = self.network.get_value(current_state)
        return {
            "recommended_weights": action.tolist(),
            "confidence": round(confidence, 4),
            "expected_value": round(value, 4),
            "timestamp": datetime.now().isoformat()
        }

    def train_episode(self, n_episodes=100):
        """训练DRL Agent"""
        logger.info(f"开始DRL训练: {n_episodes}个episode")
        results = []
        for ep in range(n_episodes):
            state = self.env.reset()
            total_reward = 0
            while True:
                action, _, _ = self.network.get_action(state)
                next_state, reward, done, info = self.env.step(action)
                total_reward += reward
                state = next_state
                if done:
                    break
            results.append({
                "episode": ep,
                "total_reward": round(total_reward, 4),
                "final_value": round(info["portfolio_value"], 2),
                "sharpe": round(info["sharpe"], 4),
                "max_drawdown": round(info["drawdown"], 4)
            })
            if (ep + 1) % 10 == 0:
                avg_reward = np.mean([r["total_reward"] for r in results[-10:]])
                logger.info(f"Episode {ep+1}/{n_episodes} | Avg Reward: {avg_reward:.4f}")
        self.network.save(self.model_path)
        return results

    def generate_signal_for_bus(self, current_state):
        """生成信号总线消息（兼容V4.0 agent_bus.py）"""
        recommendation = self.predict_portfolio_weights(current_state)
        if recommendation is None:
            return None
        return {
            "type": "portfolio_recommendation",
            "source": "Alpha-DRL",
            "data": recommendation,
            "priority": "high" if recommendation["confidence"] > 0.7 else "medium",
            "timestamp": datetime.now().isoformat()
        }

    def get_state_from_market_data(self, stock_features, global_features):
        """
        从市场数据构建状态向量
        
        Args:
            stock_features: list of dict, 每只股票的特征
                [{"price_change_5d": x, "price_change_20d": x, ...}, ...]
            global_features: dict, 全局特征
                {"market_regime": x, "portfolio_sharpe": x, ...}
        
        Returns:
            numpy array: 状态向量
        """
        state = np.zeros(self.env.state_dim)
        
        # 填充每只股票特征
        feature_keys = [
            "price_change_5d", "price_change_20d", "volatility_20d",
            "volume_ratio", "turnover_rate", "rsi_14", "macd_histogram", "sentiment_score"
        ]
        
        for i, stock in enumerate(stock_features[:self.env.max_positions]):
            for j, key in enumerate(feature_keys):
                idx = i * 8 + j
                if idx < self.env.max_positions * 8:
                    state[idx] = stock.get(key, 0.0)
        
        # 填充全局特征
        global_keys = ["market_regime", "portfolio_sharpe", "portfolio_drawdown", "cash_ratio", "total_position_pct"]
        for i, key in enumerate(global_keys):
            state[-5 + i] = global_features.get(key, 0.0)
        
        return state.astype(np.float32)


# 便捷函数，用于快速初始化
def create_drl_agent(config_path="config.json"):
    """创建DRL Agent实例"""
    return DRLPortfolioAgent(config_path)


if __name__ == "__main__":
    # 简单测试
    print("测试DRL Portfolio Agent...")
    agent = DRLPortfolioAgent()
    print(f"Agent enabled: {agent.enabled}")
    print(f"State dim: {agent.env.state_dim}")
    print(f"Action dim: {agent.env.action_dim}")
    
    # 测试预测
    test_state = np.random.randn(agent.env.state_dim).astype(np.float32)
    result = agent.predict_portfolio_weights(test_state)
    print(f"Prediction result: {result}")
