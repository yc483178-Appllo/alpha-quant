"""
Alpha-Genesis V6.1 SimEdge - Transformer-DRL 训练器
修复 4.3: Transformer-DRL 训练流程补全
====================================================
CleanRL 风格极简 PPO 实现

核心模块:
- PPOTrainer: 主训练器
- ExperienceBuffer: 经验回放缓冲
- RolloutWorker: 数据收集

训练流程:
collect_rollouts() -> compute_advantages() -> update_policy()

增量更新: 每日收盘后自动用当日数据做1 epoch微调
模型保存: checkpoint + best_model 双轨保存

Author: Alpha-Genesis Team
Version: 6.1.0
Date: 2026-03-09
"""

import os
import json
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from pathlib import Path
import logging

logger = logging.getLogger("DRLTrainer")

# 导入 Transformer-DRL Agent
try:
    from drl_portfolio_agent import TransformerPortfolioAgent
    AGENT_AVAILABLE = True
except ImportError:
    AGENT_AVAILABLE = False
    logger.warning("drl_portfolio_agent 未找到，将使用基础模型")


@dataclass
class TrainingConfig:
    """训练配置"""
    # PPO 超参数
    learning_rate: float = 3e-4
    gamma: float = 0.99          # 折扣因子
    gae_lambda: float = 0.95     # GAE lambda
    clip_epsilon: float = 0.2    # PPO clip epsilon
    value_coef: float = 0.5      # 价值函数系数
    entropy_coef: float = 0.01   # 熵正则化系数
    max_grad_norm: float = 0.5   # 梯度裁剪
    
    # 训练参数
    num_epochs: int = 4          # 每次更新迭代次数
    batch_size: int = 64         # 批次大小
    buffer_size: int = 2048      # 经验缓冲区大小
    
    # 增量更新参数
    daily_epochs: int = 1        # 每日微调 epoch 数
    daily_batch_size: int = 32   # 每日微调批次
    
    # 模型保存
    checkpoint_interval: int = 10    # 每10个episode保存checkpoint
    save_best_only: bool = True      # 只保存最佳模型


class ExperienceBuffer:
    """
    经验回放缓冲区
    存储: states, actions, rewards, values, log_probs, dones
    """
    
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.clear()
    
    def clear(self):
        """清空缓冲区"""
        self.states = []
        self.actions = []
        self.rewards = []
        self.values = []
        self.log_probs = []
        self.dones = []
        self.next_values = []
        self.position = 0
    
    def add(self, state, action, reward, value, log_prob, done, next_value=0):
        """添加经验"""
        if len(self.states) < self.capacity:
            self.states.append(state)
            self.actions.append(action)
            self.rewards.append(reward)
            self.values.append(value)
            self.log_probs.append(log_prob)
            self.dones.append(done)
            self.next_values.append(next_value)
        else:
            # 循环覆盖
            idx = self.position % self.capacity
            self.states[idx] = state
            self.actions[idx] = action
            self.rewards[idx] = reward
            self.values[idx] = value
            self.log_probs[idx] = log_prob
            self.dones[idx] = done
            self.next_values[idx] = next_value
        
        self.position += 1
    
    def get(self) -> Dict:
        """获取所有经验"""
        return {
            'states': torch.stack(self.states) if self.states else torch.tensor([]),
            'actions': torch.stack(self.actions) if self.actions else torch.tensor([]),
            'rewards': torch.tensor(self.rewards, dtype=torch.float32),
            'values': torch.tensor(self.values, dtype=torch.float32),
            'log_probs': torch.tensor(self.log_probs, dtype=torch.float32),
            'dones': torch.tensor(self.dones, dtype=torch.float32),
            'next_values': torch.tensor(self.next_values, dtype=torch.float32)
        }
    
    def __len__(self):
        return len(self.states)


class TransformerPPOModel(nn.Module):
    """
    Transformer-PPO 模型
    简化版，用于演示训练流程
    """
    
    def __init__(self, state_dim: int, action_dim: int, d_model: int = 128):
        super().__init__()
        
        self.state_dim = state_dim
        self.action_dim = action_dim
        
        # 特征编码
        self.encoder = nn.Sequential(
            nn.Linear(state_dim, d_model),
            nn.LayerNorm(d_model),
            nn.ReLU(),
            nn.Dropout(0.1)
        )
        
        # 简化 Transformer
        encoder_layer = nn.TransformerEncoderLayer(d_model=d_model, nhead=4, batch_first=True)
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=2)
        
        # 策略头 (Actor)
        self.actor = nn.Sequential(
            nn.Linear(d_model, d_model // 2),
            nn.ReLU(),
            nn.Linear(d_model // 2, action_dim)
        )
        
        # 价值头 (Critic)
        self.critic = nn.Sequential(
            nn.Linear(d_model, d_model // 2),
            nn.ReLU(),
            nn.Linear(d_model // 2, 1)
        )
    
    def forward(self, state):
        """前向传播"""
        # state: (batch, seq_len, state_dim) 或 (batch, state_dim)
        if state.dim() == 2:
            state = state.unsqueeze(1)  # 添加序列维度
        
        # 编码
        x = self.encoder(state)  # (batch, seq_len, d_model)
        
        # Transformer
        x = self.transformer(x)  # (batch, seq_len, d_model)
        x = x[:, -1, :]  # 取最后一个时间步 (batch, d_model)
        
        # 输出
        action_logits = self.actor(x)  # (batch, action_dim)
        value = self.critic(x)  # (batch, 1)
        
        return action_logits, value.squeeze(-1)
    
    def get_action_and_value(self, state, action=None):
        """获取动作和价值，用于收集经验"""
        logits, value = self.forward(state)
        
        # 计算概率分布
        probs = torch.softmax(logits, dim=-1)
        dist = torch.distributions.Categorical(probs)
        
        if action is None:
            action = dist.sample()
        
        log_prob = dist.log_prob(action)
        entropy = dist.entropy()
        
        return action, log_prob, entropy, value


class PPOTrainer:
    """
    PPO 训练器 - CleanRL 风格
    """
    
    def __init__(
        self,
        state_dim: int,
        action_dim: int,
        config: TrainingConfig = None,
        device: str = None
    ):
        self.config = config or TrainingConfig()
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        
        # 初始化模型
        self.model = TransformerPPOModel(state_dim, action_dim).to(self.device)
        self.optimizer = optim.Adam(
            self.model.parameters(),
            lr=self.config.learning_rate
        )
        
        # 经验缓冲区
        self.buffer = ExperienceBuffer(self.config.buffer_size)
        
        # 训练状态
        self.episode = 0
        self.best_reward = float('-inf')
        self.training_history = []
        
        logger.info(f"PPO 训练器初始化完成 | device: {self.device}")
    
    def collect_rollouts(self, env, num_steps: int = None) -> Dict:
        """
        收集 rollout 数据
        
        Args:
            env: 环境 (需要实现 reset() 和 step())
            num_steps: 收集步数
        
        Returns:
            经验数据字典
        """
        num_steps = num_steps or self.config.buffer_size
        
        state = env.reset()
        
        for step in range(num_steps):
            # 转换为 tensor
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            
            # 获取动作
            with torch.no_grad():
                action, log_prob, _, value = self.model.get_action_and_value(state_tensor)
            
            # 执行动作
            next_state, reward, done, info = env.step(action.cpu().item())
            
            # 存储经验
            self.buffer.add(
                state_tensor.squeeze(0),
                action,
                reward,
                value.cpu().item(),
                log_prob.cpu().item(),
                done
            )
            
            state = next_state if not done else env.reset()
        
        # 计算最后一个状态的 value
        with torch.no_grad():
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            _, _, _, last_value = self.model.get_action_and_value(state_tensor)
            last_value = last_value.cpu().item()
        
        # 填充 next_values
        for i in range(len(self.buffer)):
            if i == len(self.buffer) - 1:
                self.buffer.next_values[i] = last_value
            else:
                self.buffer.next_values[i] = self.buffer.values[i + 1]
        
        return self.buffer.get()
    
    def compute_advantages(self, rewards, values, next_values, dones) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        计算 GAE 优势函数和回报
        
        Returns:
            advantages: 优势函数值
            returns: 累积回报
        """
        advantages = []
        gae = 0
        
        for t in reversed(range(len(rewards))):
            if t == len(rewards) - 1:
                next_value = next_values[t]
            else:
                next_value = values[t + 1]
            
            delta = rewards[t] + self.config.gamma * next_value * (1 - dones[t]) - values[t]
            gae = delta + self.config.gamma * self.config.gae_lambda * (1 - dones[t]) * gae
            advantages.insert(0, gae)
        
        advantages = torch.tensor(advantages, dtype=torch.float32).to(self.device)
        returns = advantages + values
        
        # 归一化优势
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        
        return advantages, returns
    
    def update_policy(self, data: Dict) -> Dict:
        """
        更新策略（PPO）
        
        Args:
            data: 经验数据字典
        
        Returns:
            训练指标
        """
        # 提取数据
        states = data['states'].to(self.device)
        actions = data['actions'].to(self.device)
        old_log_probs = data['log_probs'].to(self.device)
        rewards = data['rewards'].to(self.device)
        values = data['values'].to(self.device)
        next_values = data['next_values'].to(self.device)
        dones = data['dones'].to(self.device)
        
        # 计算优势
        advantages, returns = self.compute_advantages(rewards, values, next_values, dones)
        
        # 多次 epoch 更新
        total_loss = 0
        total_policy_loss = 0
        total_value_loss = 0
        total_entropy = 0
        
        for epoch in range(self.config.num_epochs):
            # 生成随机索引
            indices = torch.randperm(len(states))
            
            # 小批量更新
            for start in range(0, len(states), self.config.batch_size):
                end = start + self.config.batch_size
                idx = indices[start:end]
                
                batch_states = states[idx]
                batch_actions = actions[idx]
                batch_old_log_probs = old_log_probs[idx]
                batch_advantages = advantages[idx]
                batch_returns = returns[idx]
                
                # 前向传播
                _, new_log_probs, entropy, new_values = self.model.get_action_and_value(
                    batch_states, batch_actions
                )
                
                # 计算比率
                ratio = torch.exp(new_log_probs - batch_old_log_probs)
                
                # PPO 目标
                surr1 = ratio * batch_advantages
                surr2 = torch.clamp(ratio, 1 - self.config.clip_epsilon, 1 + self.config.clip_epsilon) * batch_advantages
                policy_loss = -torch.min(surr1, surr2).mean()
                
                # 价值损失
                value_loss = nn.MSELoss()(new_values, batch_returns)
                
                # 总损失
                loss = (
                    policy_loss + 
                    self.config.value_coef * value_loss - 
                    self.config.entropy_coef * entropy.mean()
                )
                
                # 反向传播
                self.optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(self.model.parameters(), self.config.max_grad_norm)
                self.optimizer.step()
                
                total_loss += loss.item()
                total_policy_loss += policy_loss.item()
                total_value_loss += value_loss.item()
                total_entropy += entropy.mean().item()
        
        num_updates = self.config.num_epochs * (len(states) // self.config.batch_size + 1)
        
        return {
            'loss': total_loss / num_updates,
            'policy_loss': total_policy_loss / num_updates,
            'value_loss': total_value_loss / num_updates,
            'entropy': total_entropy / num_updates
        }
    
    def train_episode(self, env) -> Dict:
        """训练一个 episode"""
        # 收集数据
        data = self.collect_rollouts(env)
        
        # 更新策略
        metrics = self.update_policy(data)
        
        # 清空缓冲区
        self.buffer.clear()
        
        # 记录
        self.episode += 1
        metrics['episode'] = self.episode
        self.training_history.append(metrics)
        
        logger.info(f"Episode {self.episode} | Loss: {metrics['loss']:.4f} | "
                   f"Policy: {metrics['policy_loss']:.4f} | Value: {metrics['value_loss']:.4f}")
        
        return metrics
    
    def daily_update(self, daily_data: pd.DataFrame) -> Dict:
        """
        每日收盘后增量更新
        
        Args:
            daily_data: 当日市场数据 DataFrame
        
        Returns:
            更新指标
        """
        logger.info(f"执行每日增量更新 | 数据条数: {len(daily_data)}")
        
        # 创建临时环境
        env = MockTradingEnv(daily_data)
        
        # 收集当日数据
        data = self.collect_rollouts(env, num_steps=min(len(daily_data), 100))
        
        # 使用更小的学习率进行微调
        original_lr = self.config.learning_rate
        for param_group in self.optimizer.param_groups:
            param_group['lr'] = original_lr * 0.5  # 学习率减半
        
        # 执行更新
        metrics = {}
        for epoch in range(self.config.daily_epochs):
            epoch_metrics = self.update_policy(data)
            metrics.update(epoch_metrics)
        
        # 恢复学习率
        for param_group in self.optimizer.param_groups:
            param_group['lr'] = original_lr
        
        self.buffer.clear()
        
        logger.info(f"每日更新完成 | Loss: {metrics['loss']:.4f}")
        return metrics
    
    def save_model(self, path: str, is_best: bool = False):
        """
        保存模型
        
        Args:
            path: 保存路径
            is_best: 是否为最佳模型
        """
        save_dict = {
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'episode': self.episode,
            'best_reward': self.best_reward,
            'config': self.config.__dict__
        }
        
        # 保存 checkpoint
        checkpoint_path = Path(path) / f"checkpoint_ep{self.episode}.pt"
        torch.save(save_dict, checkpoint_path)
        
        # 保存最佳模型
        if is_best:
            best_path = Path(path) / "best_model.pt"
            torch.save(save_dict, best_path)
            logger.info(f"最佳模型已保存: {best_path}")
        
        logger.info(f"Checkpoint 已保存: {checkpoint_path}")
    
    def load_model(self, path: str):
        """加载模型"""
        checkpoint = torch.load(path, map_location=self.device)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        self.episode = checkpoint.get('episode', 0)
        self.best_reward = checkpoint.get('best_reward', float('-inf'))
        logger.info(f"模型已加载: {path} | Episode: {self.episode}")


class MockTradingEnv:
    """
    模拟交易环境（用于演示）
    实际使用时替换为真实环境
    """
    
    def __init__(self, data: pd.DataFrame, state_dim: int = 15):
        self.data = data.reset_index(drop=True)
        self.state_dim = state_dim
        self.current_step = 0
    
    def reset(self):
        self.current_step = 0
        return self._get_state()
    
    def step(self, action):
        self.current_step += 1
        
        # 模拟奖励
        reward = np.random.randn() * 0.1
        
        # 模拟 done
        done = self.current_step >= len(self.data) - 1
        
        info = {'step': self.current_step}
        
        return self._get_state(), reward, done, info
    
    def _get_state(self):
        # 返回随机状态（实际应从 data 中提取特征）
        return np.random.randn(self.state_dim).astype(np.float32)


# ═══════════════════════════════════════════════════════════
# 测试
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    # 测试训练器
    print("=== Transformer-DRL PPO 训练器测试 ===\n")
    
    # 创建训练器
    trainer = PPOTrainer(
        state_dim=15,
        action_dim=5,
        config=TrainingConfig(num_epochs=2, batch_size=32, buffer_size=256)
    )
    
    # 创建模拟环境
    mock_data = pd.DataFrame({'price': range(100)})
    env = MockTradingEnv(mock_data, state_dim=15)
    
    # 训练几个 episode
    print("训练 3 个 episodes:")
    for i in range(3):
        metrics = trainer.train_episode(env)
        print(f"Episode {i+1}: Loss={metrics['loss']:.4f}")
    
    # 测试每日更新
    print("\n每日增量更新测试:")
    daily_data = pd.DataFrame({'price': range(50)})
    daily_metrics = trainer.daily_update(daily_data)
    print(f"Daily Update: Loss={daily_metrics['loss']:.4f}")
    
    # 测试保存
    print("\n模型保存测试:")
    os.makedirs("./models", exist_ok=True)
    trainer.save_model("./models", is_best=True)
    
    print("\n✅ 训练器测试完成")
