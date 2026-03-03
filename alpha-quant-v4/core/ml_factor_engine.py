# ml_factor_engine.py --- 机器学习因子合成
# 用随机森林对多因子进行权重优化，替代手动设定权重

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score, classification_report
from loguru import logger

class MLFactorEngine:
    """
    机器学习因子合成引擎

    原理：
    1. 构建历史因子数据集（换手率、量比、PE、PB、涨跌幅等）
    2. 标签：未来5日收益>3%为正样本，<-2%为负样本
    3. 训练随机森林/XGBoost模型
    4. 输出因子重要度 → 替代手动权重
    """

    def __init__(self, model_type="rf"):
        if model_type == "rf":
            self.model = RandomForestClassifier(
                n_estimators=100, max_depth=8, min_samples_leaf=20,
                random_state=42, n_jobs=-1
            )
        elif model_type == "gbdt":
            self.model = GradientBoostingClassifier(
                n_estimators=100, max_depth=5, learning_rate=0.1,
                random_state=42
            )
        self.feature_names = []
        self.is_trained = False

    def prepare_features(self, df):
        """
        从A股行情数据构建特征矩阵

        参数:
            df: AkShare stock_zh_a_spot_em() 的输出
        """
        features = pd.DataFrame()
        features["turnover"] = pd.to_numeric(df["换手率"], errors="coerce")
        features["volume_ratio"] = pd.to_numeric(df["量比"], errors="coerce")
        features["change_pct"] = pd.to_numeric(df["涨跌幅"], errors="coerce")
        features["pe_ttm"] = pd.to_numeric(df.get("市盈率-动态", 0), errors="coerce")
        features["pb"] = pd.to_numeric(df.get("市净率", 0), errors="coerce")
        features["amplitude"] = pd.to_numeric(df.get("振幅", 0), errors="coerce")
        features["market_cap_log"] = np.log1p(pd.to_numeric(df["总市值"], errors="coerce"))

        # 衍生特征
        features["turnover_volume_ratio"] = features["turnover"] * features["volume_ratio"]
        features["pe_pb_ratio"] = features["pe_ttm"] / features["pb"].replace(0, np.nan)
        features["momentum_score"] = features["change_pct"] * features["volume_ratio"]

        self.feature_names = features.columns.tolist()
        return features.fillna(0)

    def train(self, X, y):
        """训练模型（使用时间序列交叉验证）"""
        tscv = TimeSeriesSplit(n_splits=5)
        scores = []

        for train_idx, val_idx in tscv.split(X):
            X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

            self.model.fit(X_train, y_train)
            score = accuracy_score(y_val, self.model.predict(X_val))
            scores.append(score)

        # 最终在全量数据上训练
        self.model.fit(X, y)
        self.is_trained = True

        avg_score = np.mean(scores)
        logger.info(f"ML模型训练完成 | 交叉验证平均准确率: {avg_score:.2%}")
        return avg_score

    def get_factor_importance(self):
        """获取因子重要度排名"""
        if not self.is_trained:
            logger.error("模型尚未训练")
            return {}

        importance = dict(zip(self.feature_names, self.model.feature_importances_))
        sorted_importance = dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))

        logger.info("因子重要度排名:")
        for name, score in sorted_importance.items():
            logger.info(f"  {name}: {score:.4f}")

        return sorted_importance

    def predict_score(self, X):
        """对新数据预测评分"""
        if not self.is_trained:
            return np.zeros(len(X))

        # 返回正类的概率作为评分
        proba = self.model.predict_proba(X)
        if proba.shape[1] >= 2:
            return proba[:, 1]
        return proba[:, 0]

if __name__ == "__main__":
    # 示例：用模拟数据展示工作流程
    np.random.seed(42)
    n = 500
    data = pd.DataFrame({
        "换手率": np.random.uniform(1, 15, n),
        "量比": np.random.uniform(0.5, 5, n),
        "涨跌幅": np.random.uniform(-5, 8, n),
        "市盈率-动态": np.random.uniform(5, 50, n),
        "市净率": np.random.uniform(0.5, 5, n),
        "振幅": np.random.uniform(1, 10, n),
        "总市值": np.random.uniform(20e8, 2000e8, n),
    })
    labels = pd.Series(np.random.choice([0, 1], n, p=[0.6, 0.4]))

    engine = MLFactorEngine(model_type="rf")
    X = engine.prepare_features(data)
    accuracy = engine.train(X, labels)
    importance = engine.get_factor_importance()

    print(f"\n模型准确率: {accuracy:.2%}")
    print("\n因子重要度:")
    for k, v in importance.items():
        print(f"  {k}: {v:.4f}")
