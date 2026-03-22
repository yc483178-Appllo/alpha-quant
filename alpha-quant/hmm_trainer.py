"""
Alpha-Genesis V6.1 SimEdge - HMM 市场政权检测训练器
修复 4.4: HMM 模型训练流程补全
======================================================
滚动窗口训练 + 每周自动重训练

Author: Alpha-Genesis Team
Version: 6.1.0
Date: 2026-03-09
"""

import os
import json
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from pathlib import Path

# HMM 库
try:
    from hmmlearn.hmm import GaussianHMM
    HMM_AVAILABLE = True
except ImportError:
    HMM_AVAILABLE = False
    logging.warning("hmmlearn 未安装，HMM 功能将使用模拟实现")

# sklearn
try:
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = logging.getLogger("HMMTrainer")


class MarketRegimeHMMTrainer:
    """
    市场政权 HMM 训练器
    
    功能:
    - 滚动窗口训练
    - 自动特征工程
    - 模型持久化
    - 每周自动重训练
    """
    
    def __init__(
        self,
        n_regimes: int = 4,
        n_features: int = 4,
        window_days: int = 252,
        retrain_interval_days: int = 7,
        model_path: str = "./models/hmm_regime.pkl"
    ):
        """
        初始化 HMM 训练器
        
        Args:
            n_regimes: 政权数量 (默认4: bull/bear/range/crisis)
            n_features: 特征维度
            window_days: 滚动窗口天数
            retrain_interval_days: 重训练间隔(天)
            model_path: 模型保存路径
        """
        self.n_regimes = n_regimes
        self.n_features = n_features
        self.window_days = window_days
        self.retrain_interval_days = retrain_interval_days
        self.model_path = Path(model_path)
        
        # 模型和预处理器
        self.model = None
        self.scaler = StandardScaler() if SKLEARN_AVAILABLE else None
        
        # 训练状态
        self.last_train_date = None
        self.training_history = []
        
        # 尝试加载已有模型
        self._load_model()
        
        logger.info(f"HMM 训练器初始化完成 | regimes: {n_regimes} | window: {window_days}天")
    
    def _load_model(self):
        """加载已有模型"""
        if self.model_path.exists():
            try:
                import joblib
                data = joblib.load(self.model_path)
                self.model = data.get('model')
                self.scaler = data.get('scaler', StandardScaler())
                self.last_train_date = data.get('last_train_date')
                logger.info(f"已加载 HMM 模型: {self.model_path}")
            except Exception as e:
                logger.warning(f"加载模型失败: {e}")
                self.model = None
    
    def _save_model(self):
        """保存模型"""
        try:
            import joblib
            self.model_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                'model': self.model,
                'scaler': self.scaler,
                'last_train_date': self.last_train_date,
                'n_regimes': self.n_regimes,
                'n_features': self.n_features
            }
            joblib.dump(data, self.model_path)
            logger.info(f"HMM 模型已保存: {self.model_path}")
        except Exception as e:
            logger.error(f"保存模型失败: {e}")
    
    def extract_features(self, df: pd.DataFrame) -> np.ndarray:
        """
        从原始数据提取 HMM 特征
        
        Args:
            df: DataFrame 包含价格数据
                - close: 收盘价
                - volume: 成交量(可选)
                - high: 最高价(可选)
                - low: 最低价(可选)
        
        Returns:
            特征矩阵 (n_samples, n_features)
        """
        features = pd.DataFrame(index=df.index)
        
        # 1. 对数收益率
        features['returns'] = np.log(df['close'] / df['close'].shift(1))
        
        # 2. 波动率 (20日滚动标准差)
        features['volatility'] = features['returns'].rolling(window=20).std()
        
        # 3. 成交量变化率 (如果有)
        if 'volume' in df.columns:
            features['volume_change'] = df['volume'].pct_change()
        else:
            # 使用价格波动替代
            features['volume_change'] = features['returns'].abs()
        
        # 4. 价格动量 (10日)
        features['momentum'] = df['close'].pct_change(periods=10)
        
        # 5. 高低价差 (如果有)
        if 'high' in df.columns and 'low' in df.columns:
            features['range'] = (df['high'] - df['low']) / df['close']
        else:
            features['range'] = features['returns'].abs()
        
        # 选择需要的特征
        feature_cols = ['returns', 'volatility', 'volume_change', 'momentum']
        features = features[feature_cols].dropna()
        
        return features.values
    
    def train(self, df: pd.DataFrame, force: bool = False) -> Dict:
        """
        训练 HMM 模型
        
        Args:
            df: 历史数据 DataFrame
            force: 强制重训练，忽略间隔检查
        
        Returns:
            训练结果
        """
        # 检查是否需要重训练
        if not force and self.last_train_date:
            days_since_train = (datetime.now() - self.last_train_date).days
            if days_since_train < self.retrain_interval_days:
                logger.info(f"距离上次训练仅 {days_since_train} 天，跳过")
                return {'status': 'skipped', 'days_since_train': days_since_train}
        
        # 提取特征
        features = self.extract_features(df)
        
        if len(features) < self.window_days:
            logger.warning(f"数据不足: {len(features)} < {self.window_days}")
            return {'status': 'failed', 'reason': 'insufficient_data'}
        
        # 使用滚动窗口数据
        train_data = features[-self.window_days:]
        
        # 标准化
        if self.scaler:
            train_data = self.scaler.fit_transform(train_data)
        
        # 训练 HMM
        if HMM_AVAILABLE:
            try:
                self.model = GaussianHMM(
                    n_components=self.n_regimes,
                    covariance_type="full",
                    n_iter=100,
                    random_state=42
                )
                self.model.fit(train_data)
                
                self.last_train_date = datetime.now()
                
                # 保存模型
                self._save_model()
                
                # 记录训练历史
                result = {
                    'status': 'success',
                    'train_date': self.last_train_date.isoformat(),
                    'n_samples': len(train_data),
                    'log_likelihood': self.model.score(train_data),
                    'converged': self.model.monitor_.converged,
                    'n_iter': self.model.n_iter
                }
                self.training_history.append(result)
                
                logger.info(f"HMM 训练完成 | log_likelihood: {result['log_likelihood']:.2f} | "
                           f"converged: {result['converged']}")
                
                return result
                
            except Exception as e:
                logger.error(f"HMM 训练失败: {e}")
                return {'status': 'failed', 'reason': str(e)}
        else:
            # 模拟训练
            logger.warning("使用模拟 HMM 训练")
            self.last_train_date = datetime.now()
            return {
                'status': 'mock_success',
                'train_date': self.last_train_date.isoformat(),
                'note': 'hmmlearn not installed'
            }
    
    def predict(self, recent_data: pd.DataFrame) -> Dict:
        """
        预测当前市场政权
        
        Args:
            recent_data: 最近几天的数据
        
        Returns:
            预测结果
        """
        if self.model is None:
            logger.warning("模型未训练，无法预测")
            return {'regime': 'unknown', 'confidence': 0}
        
        features = self.extract_features(recent_data)
        
        if len(features) == 0:
            return {'regime': 'unknown', 'confidence': 0}
        
        # 使用最新数据
        latest = features[-1:]
        if self.scaler:
            latest = self.scaler.transform(latest)
        
        # 预测
        if HMM_AVAILABLE:
            regime = self.model.predict(latest)[0]
            # 计算置信度 (使用后验概率)
            posteriors = self.model.predict_proba(latest)[0]
            confidence = float(posteriors[regime])
            
            # 政权名称映射
            regime_names = ['bull', 'bear', 'range', 'crisis']
            regime_name = regime_names[regime] if regime < len(regime_names) else f'regime_{regime}'
            
            return {
                'regime': regime_name,
                'regime_id': int(regime),
                'confidence': round(confidence, 4),
                'posteriors': posteriors.tolist()
            }
        else:
            # 模拟预测
            import random
            regime_names = ['bull', 'bear', 'range', 'crisis']
            regime = random.randint(0, 3)
            return {
                'regime': regime_names[regime],
                'regime_id': regime,
                'confidence': round(random.uniform(0.6, 0.9), 4),
                'note': 'mock_prediction'
            }
    
    def auto_retrain_check(self, df: pd.DataFrame) -> Dict:
        """
        自动重训练检查
        
        Returns:
            检查结果和训练结果(如果需要)
        """
        need_retrain = False
        
        if self.last_train_date is None:
            need_retrain = True
            reason = "模型未训练"
        else:
            days_since = (datetime.now() - self.last_train_date).days
            if days_since >= self.retrain_interval_days:
                need_retrain = True
                reason = f"距离上次训练 {days_since} 天，超过 {self.retrain_interval_days} 天阈值"
            else:
                reason = f"无需重训练，距离上次仅 {days_since} 天"
        
        if need_retrain:
            logger.info(f"触发自动重训练: {reason}")
            result = self.train(df)
            result['trigger_reason'] = reason
            return result
        else:
            return {'status': 'no_action_needed', 'reason': reason}
    
    def get_regime_statistics(self, df: pd.DataFrame) -> Dict:
        """
        获取各政权的统计特征
        
        Returns:
            各政权的平均收益率、波动率等统计
        """
        if self.model is None:
            return {'error': '模型未训练'}
        
        features = self.extract_features(df)
        if self.scaler:
            features_scaled = self.scaler.transform(features)
        else:
            features_scaled = features
        
        if HMM_AVAILABLE:
            regimes = self.model.predict(features_scaled)
            
            stats = {}
            for regime_id in range(self.n_regimes):
                mask = regimes == regime_id
                if mask.sum() > 0:
                    regime_features = features[mask]
                    stats[f'regime_{regime_id}'] = {
                        'count': int(mask.sum()),
                        'avg_return': round(float(regime_features[:, 0].mean()), 4),
                        'avg_volatility': round(float(regime_features[:, 1].mean()), 4),
                        'avg_momentum': round(float(regime_features[:, 3].mean()), 4)
                    }
            
            return stats
        else:
            return {'note': 'hmmlearn not installed'}


# ═══════════════════════════════════════════════════════════
# 便捷函数
# ═══════════════════════════════════════════════════════════

def train_hmm_model(
    df: pd.DataFrame,
    n_regimes: int = 4,
    save_path: str = "./models/hmm_regime.pkl"
) -> MarketRegimeHMMTrainer:
    """
    便捷函数: 训练 HMM 模型
    
    Args:
        df: 历史数据
        n_regimes: 政权数量
        save_path: 保存路径
    
    Returns:
        训练好的 HMM 训练器
    """
    trainer = MarketRegimeHMMTrainer(
        n_regimes=n_regimes,
        model_path=save_path
    )
    
    result = trainer.train(df, force=True)
    logger.info(f"HMM 模型训练结果: {result}")
    
    return trainer


def detect_market_regime(
    recent_data: pd.DataFrame,
    model_path: str = "./models/hmm_regime.pkl"
) -> Dict:
    """
    便捷函数: 检测当前市场政权
    
    Args:
        recent_data: 最近数据
        model_path: 模型路径
    
    Returns:
        政权预测结果
    """
    trainer = MarketRegimeHMMTrainer(model_path=model_path)
    return trainer.predict(recent_data)


# ═══════════════════════════════════════════════════════════
# 测试
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=== HMM 市场政权检测训练器测试 ===\n")
    
    # 生成模拟数据
    np.random.seed(42)
    dates = pd.date_range(end=datetime.now(), periods=300, freq='B')
    
    # 模拟股价数据 (带政权切换特征)
    prices = [100]
    for i in range(299):
        # 模拟不同政权的收益率特征
        if i < 100:  # 牛市
            ret = np.random.normal(0.001, 0.01)
        elif i < 150:  # 熊市
            ret = np.random.normal(-0.001, 0.02)
        elif i < 220:  # 震荡
            ret = np.random.normal(0, 0.008)
        else:  # 危机
            ret = np.random.normal(-0.002, 0.03)
        prices.append(prices[-1] * (1 + ret))
    
    df = pd.DataFrame({
        'close': prices,
        'high': [p * (1 + abs(np.random.randn()) * 0.01) for p in prices],
        'low': [p * (1 - abs(np.random.randn()) * 0.01) for p in prices],
        'volume': np.random.randint(1000000, 10000000, 300)
    }, index=dates)
    
    # 测试训练
    print("1. 测试 HMM 训练:")
    trainer = MarketRegimeHMMTrainer(n_regimes=4, window_days=100)
    result = trainer.train(df, force=True)
    print(f"   训练结果: {result['status']}")
    if result['status'] == 'success':
        print(f"   log_likelihood: {result['log_likelihood']:.2f}")
        print(f"   converged: {result['converged']}")
    
    # 测试预测
    print("\n2. 测试政权预测:")
    prediction = trainer.predict(df.tail(20))
    print(f"   当前政权: {prediction['regime']}")
    print(f"   置信度: {prediction['confidence']:.2%}")
    
    # 测试自动重训练检查
    print("\n3. 测试自动重训练检查:")
    check_result = trainer.auto_retrain_check(df)
    print(f"   结果: {check_result['status']}")
    
    # 测试统计
    print("\n4. 测试政权统计:")
    stats = trainer.get_regime_statistics(df)
    for regime, data in stats.items():
        if isinstance(data, dict):
            print(f"   {regime}: count={data['count']}, avg_return={data['avg_return']:.4f}")
    
    print("\n✅ HMM 训练器测试完成")
