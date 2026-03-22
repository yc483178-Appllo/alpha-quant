# Alpha-Genesis V7.0 - 第四章：Claude创新增强

## 第四章：Claude创新增强（4项前沿技术）

**定位：超出用户方案的前沿技术创新，将系统提升到行业领先水平**

---

## 4.1 GNN股票关系图网络

### 创新背景

**现有系统局限：**
- 把每只股票当作独立个体分析
- 忽略了股票之间的复杂关系网络
- 无法捕捉行业联动、供应链传导、资金流动等效应

**GNN解决方案：**
- 建模股票间的多种关系类型
- 捕捉信息/风险传导路径
- 提前预测联动效应

```python
# gnn_stock_graph.py
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GATConv, HeteroConv, Linear
from torch_geometric.data import HeteroData
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional


class StockRelationGraph:
    """
    股票关系图网络
    
    构建多类型边的异构图：
    - 供应链关系：上下游企业联动
    - 股权关系：共同股东/交叉持股
    - 行业关系：同行业联动
    - 资金流关系：北向资金/融资融券联动
    """
    
    EDGE_TYPES = [
        ('stock', 'supply_chain', 'stock'),    # 供应链
        ('stock', 'ownership', 'stock'),       # 股权关系
        ('stock', 'industry', 'stock'),        # 行业关系
        ('stock', 'capital_flow', 'stock'),    # 资金流
        ('stock', 'correlation', 'stock'),     # 价格相关性
    ]
    
    def __init__(
        self,
        n_stocks: int = 500,
        node_feature_dim: int = 64,
        hidden_dim: int = 128,
        n_heads: int = 8,
        n_layers: int = 3
    ):
        self.n_stocks = n_stocks
        self.node_feature_dim = node_feature_dim
        self.hidden_dim = hidden_dim
        
        # 图注意力网络
        self.gat = GraphAttentionNetwork(
            n_heads=n_heads,
            hidden_dim=hidden_dim,
            edge_types=self.EDGE_TYPES,
            n_layers=n_layers
        )
        
        # 节点特征编码器
        self.node_encoder = nn.Sequential(
            nn.Linear(node_feature_dim, hidden_dim),
            nn.ReLU(),
            nn.LayerNorm(hidden_dim)
        )
        
        # 关系预测头
        self.contagion_predictor = ContagionPredictor(hidden_dim)
        
    def build_graph(
        self,
        stock_universe: List[str],
        supply_chain_data: pd.DataFrame,
        ownership_data: pd.DataFrame,
        industry_data: pd.DataFrame,
        capital_flow_data: pd.DataFrame,
        price_correlation: pd.DataFrame
    ) -> HeteroData:
        """
        构建异构图
        
        Args:
            supply_chain_data: 供应链关系 DataFrame [upstream, downstream, weight]
            ownership_data: 股权关系 DataFrame [stock1, stock2, common_holder_pct]
            industry_data: 行业分类 DataFrame [code, industry_code]
            capital_flow_data: 资金流向 DataFrame [date, code, northbound_flow]
            price_correlation: 价格相关性矩阵
        """
        data = HeteroData()
        
        # 节点特征 (初始化)
        node_features = torch.randn(len(stock_universe), self.node_feature_dim)
        data['stock'].x = node_features
        data['stock'].code = stock_universe
        
        # 构建边索引
        # 1. 供应链边
        supply_edges = self._build_supply_chain_edges(
            supply_chain_data, stock_universe
        )
        data['stock', 'supply_chain', 'stock'].edge_index = supply_edges['indices']
        data['stock', 'supply_chain', 'stock'].edge_attr = supply_edges['weights']
        
        # 2. 股权边
        ownership_edges = self._build_ownership_edges(
            ownership_data, stock_universe
        )
        data['stock', 'ownership', 'stock'].edge_index = ownership_edges['indices']
        data['stock', 'ownership', 'stock'].edge_attr = ownership_edges['weights']
        
        # 3. 行业边 (同行业的股票相连)
        industry_edges = self._build_industry_edges(
            industry_data, stock_universe
        )
        data['stock', 'industry', 'stock'].edge_index = industry_edges['indices']
        
        # 4. 资金流边
        capital_edges = self._build_capital_flow_edges(
            capital_flow_data, stock_universe
        )
        data['stock', 'capital_flow', 'stock'].edge_index = capital_edges['indices']
        data['stock', 'capital_flow', 'stock'].edge_attr = capital_edges['weights']
        
        # 5. 相关性边 (高相关的股票相连)
        corr_edges = self._build_correlation_edges(
            price_correlation, stock_universe, threshold=0.7
        )
        data['stock', 'correlation', 'stock'].edge_index = corr_edges['indices']
        data['stock', 'correlation', 'stock'].edge_attr = corr_edges['weights']
        
        return data
    
    def _build_supply_chain_edges(
        self,
        supply_data: pd.DataFrame,
        stock_universe: List[str]
    ) -> Dict:
        """构建供应链边"""
        code_to_idx = {code: i for i, code in enumerate(stock_universe)}
        
        edges = []
        weights = []
        
        for _, row in supply_data.iterrows():
            upstream = row.get('upstream')
            downstream = row.get('downstream')
            
            if upstream in code_to_idx and downstream in code_to_idx:
                edges.append([code_to_idx[upstream], code_to_idx[downstream]])
                weights.append(row.get('relationship_strength', 1.0))
        
        return {
            'indices': torch.tensor(edges, dtype=torch.long).t().contiguous(),
            'weights': torch.tensor(weights, dtype=torch.float)
        }
    
    def _build_ownership_edges(
        self,
        ownership_data: pd.DataFrame,
        stock_universe: List[str]
    ) -> Dict:
        """构建股权关系边"""
        code_to_idx = {code: i for i, code in enumerate(stock_universe)}
        
        edges = []
        weights = []
        
        for _, row in ownership_data.iterrows():
            stock1 = row.get('stock1')
            stock2 = row.get('stock2')
            
            if stock1 in code_to_idx and stock2 in code_to_idx:
                edges.append([code_to_idx[stock1], code_to_idx[stock2]])
                # 共同股东比例作为权重
                weights.append(row.get('common_holder_pct', 0.5))
        
        return {
            'indices': torch.tensor(edges, dtype=torch.long).t().contiguous(),
            'weights': torch.tensor(weights, dtype=torch.float)
        }
    
    def _build_industry_edges(
        self,
        industry_data: pd.DataFrame,
        stock_universe: List[str]
    ) -> Dict:
        """构建行业关系边 (同行业股票全连接)"""
        code_to_idx = {code: i for i, code in enumerate(stock_universe)}
        
        # 按行业分组
        industry_groups = industry_data.groupby('industry_code')['code'].apply(list)
        
        edges = []
        for industry, codes in industry_groups.items():
            valid_codes = [c for c in codes if c in code_to_idx]
            
            # 行业内全连接
            for i, code1 in enumerate(valid_codes):
                for code2 in valid_codes[i+1:]:
                    edges.append([code_to_idx[code1], code_to_idx[code2]])
                    edges.append([code_to_idx[code2], code_to_idx[code1]])  # 双向
        
        return {
            'indices': torch.tensor(edges, dtype=torch.long).t().contiguous(),
            'weights': torch.ones(len(edges))
        }
    
    def _build_capital_flow_edges(
        self,
        flow_data: pd.DataFrame,
        stock_universe: List[str],
        top_n: int = 10
    ) -> Dict:
        """构建资金流关系边 (北向资金同向流入的股票相连)"""
        code_to_idx = {code: i for i, code in enumerate(stock_universe)}
        
        # 计算资金流的相似性
        flow_matrix = flow_data.pivot(index='date', columns='code', values='northbound_flow')
        flow_matrix = flow_matrix.fillna(0)
        
        # 相关性
        correlation = flow_matrix.corr()
        
        edges = []
        weights = []
        
        for code1 in correlation.columns:
            if code1 not in code_to_idx:
                continue
            
            # 取相关性最高的top_n
            top_corr = correlation[code1].nlargest(top_n + 1)[1:]  # 排除自己
            
            for code2, corr in top_corr.items():
                if code2 in code_to_idx and corr > 0.5:  # 阈值
                    edges.append([code_to_idx[code1], code_to_idx[code2]])
                    weights.append(corr)
        
        return {
            'indices': torch.tensor(edges, dtype=torch.long).t().contiguous(),
            'weights': torch.tensor(weights, dtype=torch.float)
        }
    
    def _build_correlation_edges(
        self,
        price_corr: pd.DataFrame,
        stock_universe: List[str],
        threshold: float = 0.7
    ) -> Dict:
        """构建价格相关性边"""
        code_to_idx = {code: i for i, code in enumerate(stock_universe)}
        
        edges = []
        weights = []
        
        for code1 in price_corr.columns:
            if code1 not in code_to_idx:
                continue
            
            for code2 in price_corr.index:
                if code2 not in code_to_idx or code1 >= code2:
                    continue
                
                corr = price_corr.loc[code2, code1]
                if abs(corr) > threshold:
                    edges.append([code_to_idx[code1], code_to_idx[code2]])
                    weights.append(abs(corr))
        
        return {
            'indices': torch.tensor(edges, dtype=torch.long).t().contiguous(),
            'weights': torch.tensor(weights, dtype=torch.float)
        }
    
    def predict_contagion(
        self,
        graph: HeteroData,
        shock_stock: str,
        magnitude: float
    ) -> Dict[str, float]:
        """
        ★ 核心应用：预测风险/机会传导效应
        
        当某只股票发生异动时，预测对其他股票的影响
        
        Args:
            shock_stock: 异动的股票代码
            magnitude: 异动幅度 (如-0.08表示跌8%)
            
        Returns:
            {股票代码: 预测影响度}
            
        应用场景：
        - 宁德时代暴跌 → 自动计算对下游车企、电池供应商的传导
        - 提前调整持仓，规避连锁下跌风险
        """
        self.gat.eval()
        
        with torch.no_grad():
            # 节点编码
            x_encoded = self.node_encoder(graph['stock'].x)
            
            # 图注意力传播
            node_embeddings = self.gat(graph, x_encoded)
            
            # 找到冲击股票对应的节点
            stock_codes = graph['stock'].code
            if shock_stock not in stock_codes:
                return {}
            
            shock_idx = stock_codes.index(shock_stock)
            
            # 预测传导效应
            propagation = self.contagion_predictor.predict(
                node_embeddings,
                shock_idx,
                magnitude
            )
            
        # 转换为股票代码映射
        result = {}
        for idx, impact in enumerate(propagation):
            if idx != shock_idx and abs(impact) > 0.01:  # 忽略自己和小影响
                result[stock_codes[idx]] = float(impact)
        
        # 按影响度排序
        result = dict(sorted(result.items(), key=lambda x: abs(x[1]), reverse=True))
        
        return result
    
    def update_node_features(
        self,
        graph: HeteroData,
        new_features: Dict[str, np.ndarray]
    ) -> HeteroData:
        """更新节点特征 (实时)"""
        for code, features in new_features.items():
            if code in graph['stock'].code:
                idx = graph['stock'].code.index(code)
                graph['stock'].x[idx] = torch.tensor(features, dtype=torch.float)
        
        return graph


class GraphAttentionNetwork(nn.Module):
    """
    异构图注意力网络
    
    处理多种类型的边关系
    """
    
    def __init__(
        self,
        n_heads: int,
        hidden_dim: int,
        edge_types: List[Tuple],
        n_layers: int = 3
    ):
        super().__init__()
        
        self.convs = nn.ModuleList()
        
        for _ in range(n_layers):
            conv_dict = {}
            for edge_type in edge_types:
                conv_dict[edge_type] = GATConv(
                    hidden_dim,
                    hidden_dim // n_heads,
                    heads=n_heads,
                    concat=True,
                    dropout=0.2,
                    edge_dim=1  # 边权重维度
                )
            
            self.convs.append(HeteroConv(conv_dict, aggr='mean'))
    
    def forward(self, graph: HeteroData, x: torch.Tensor) -> torch.Tensor:
        """
        前向传播
        
        Args:
            graph: 异构图数据
            x: 节点特征 [N, hidden_dim]
            
        Returns:
            节点嵌入 [N, hidden_dim]
        """
        # 构建x_dict
        x_dict = {'stock': x}
        
        # 多层传播
        for conv in self.convs:
            x_dict = conv(x_dict, graph.edge_index_dict, graph.edge_attr_dict)
            x_dict = {key: F.relu(x) for key, x in x_dict.items()}
        
        return x_dict['stock']


class ContagionPredictor(nn.Module):
    """
    传导效应预测器
    
    预测一个节点的冲击如何传播到整个图
    """
    
    def __init__(self, hidden_dim: int):
        super().__init__()
        
        self.impact_mlp = nn.Sequential(
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1)
        )
    
    def predict(
        self,
        node_embeddings: torch.Tensor,
        shock_idx: int,
        magnitude: float
    ) -> torch.Tensor:
        """
        预测传导效应
        
        Args:
            node_embeddings: 所有节点的嵌入 [N, hidden_dim]
            shock_idx: 冲击节点的索引
            magnitude: 冲击幅度
            
        Returns:
            每个节点的预测影响 [N]
        """
        n_nodes = node_embeddings.size(0)
        
        # 冲击节点的嵌入
        shock_embed = node_embeddings[shock_idx].unsqueeze(0).expand(n_nodes, -1)
        
        # 拼接冲击节点和每个节点的嵌入
        combined = torch.cat([shock_embed, node_embeddings], dim=1)
        
        # 预测影响度
        raw_impact = self.impact_mlp(combined).squeeze(-1)
        
        # 根据冲击幅度缩放
        impact = torch.tanh(raw_impact) * magnitude
        
        # 冲击节点自身的影响就是原始冲击
        impact[shock_idx] = magnitude
        
        return impact


# 应用场景示例
"""
# 1. 构建股票关系图
graph_builder = StockRelationGraph(n_stocks=500)

# 加载关系数据
supply_chain = pd.read_csv('supply_chain.csv')  # 供应链数据
ownership = pd.read_csv('ownership.csv')        # 股权数据
industry = pd.read_csv('industry.csv')          # 行业分类
capital_flow = pd.read_csv('northbound.csv')    # 北向资金
price_corr = pd.read_csv('correlation.csv')     # 价格相关性

stock_universe = load_hs300_components()  # 沪深300成分股

# 构建图
graph = graph_builder.build_graph(
    stock_universe,
    supply_chain,
    ownership,
    industry,
    capital_flow,
    price_corr
)

# 2. 实时监控与预警
monitor = StockGraphMonitor(graph_builder, graph)

# 宁德时代大跌8%
contagion = graph_builder.predict_contagion(
    graph,
    shock_stock='300750',  # 宁德时代
    magnitude=-0.08        # 跌8%
)

print("风险传导预测：")
for code, impact in list(contagion.items())[:10]:
    print(f"  {code}: {impact:+.2%}")

# 输出示例：
# 300750: -8.00%  (宁德时代本身)
# 002594: -5.20%  (比亚迪，下游客户)
# 603659: -4.80%  (璞泰来，上游材料)
# 300073: -4.50%  (当升科技，同行业)
# ...

# 3. 自动调整持仓
if any(abs(impact) > 0.05 for impact in contagion.values()):
    # 触发风控：减仓相关股票
    risk_manager.reduce_exposure(
        stocks=list(contagion.keys()),
        reason=f" contagion from {shock_stock}"
    )
"""


class StockGraphMonitor:
    """
    股票关系图实时监控
    
    监控图中节点的异常变动，及时预警
    """
    
    def __init__(
        self,
        graph_builder: StockRelationGraph,
        base_graph: HeteroData,
        alert_threshold: float = 0.05
    ):
        self.builder = graph_builder
        self.graph = base_graph
        self.alert_threshold = alert_threshold
        
        self.price_history = {}
        self.active_alerts = []
    
    def update_price(self, code: str, price: float, timestamp: datetime):
        """更新价格并检测异常"""
        if code not in self.price_history:
            self.price_history[code] = []
        
        self.price_history[code].append({
            'price': price,
            'timestamp': timestamp
        })
        
        # 保持最近100个价格
        if len(self.price_history[code]) > 100:
            self.price_history[code].pop(0)
        
        # 检测异常变动
        if len(self.price_history[code]) >= 2:
            prev_price = self.price_history[code][-2]['price']
            change = (price - prev_price) / prev_price
            
            if abs(change) >= self.alert_threshold:
                self._handle_anomaly(code, change, timestamp)
    
    def _handle_anomaly(self, code: str, change: float, timestamp: datetime):
        """处理异常变动"""
        # 预测传导效应
        contagion = self.builder.predict_contagion(self.graph, code, change)
        
        alert = {
            'timestamp': timestamp,
            'source_stock': code,
            'change': change,
            'affected_stocks': contagion,
            'severity': 'high' if abs(change) > 0.07 else 'medium'
        }
        
        self.active_alerts.append(alert)
        
        # 发送预警
        self._send_alert(alert)
    
    def _send_alert(self, alert: Dict):
        """发送预警通知"""
        print(f"[GNN Alert] {alert['timestamp']}")
        print(f"  Source: {alert['source_stock']} {alert['change']:+.2%}")
        print(f"  Affected stocks: {len(alert['affected_stocks'])}")
        print(f"  Top impacts:")
        for code, impact in list(alert['affected_stocks'].items())[:5]:
            print(f"    {code}: {impact:+.2%}")


---

*Module: 4.1 GNN Stock Relation Graph Network*  
*Chapter: 4*  
*Status: 详细设计记录*
