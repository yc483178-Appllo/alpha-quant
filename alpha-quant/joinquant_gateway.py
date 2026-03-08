"""
聚宽数据网关 - V6.0 新增模块
文件: joinquant_gateway.py
功能: 整合聚宽JoinQuant数据到现有数据层
依赖: jqdatasdk==1.8.16, pandas, numpy, logging
注意: 需要聚宽账号，免费版每日数据量500次/天
"""

import os
import json
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Dict, List, Optional

logger = logging.getLogger("JoinQuantGateway")


class JoinQuantAuth:
    """聚宽API认证管理"""
    _authenticated = False
    _jq = None
    
    @classmethod
    def authenticate(cls, username: str, password: str) -> bool:
        """初始化聚宽连接"""
        try:
            import jqdatasdk as jq
            jq.auth(username, password)
            cls._jq = jq
            cls._authenticated = True
            logger.info(f"聚宽认证成功: {username}")
            return True
        except ImportError:
            logger.error("未安装jqdatasdk，请运行: pip install jqdatasdk")
            return False
        except Exception as e:
            logger.error(f"聚宽认证失败: {e}")
            return False
    
    @classmethod
    def get_client(cls):
        """获取已认证的聚宽客户端"""
        if not cls._authenticated:
            raise RuntimeError("聚宽未认证，请先调用authenticate()")
        return cls._jq


class JoinQuantDataGateway:
    """
    聚宽数据获取主类
    提供: 基本面/因子/行业/机构持仓/公司行动 数据
    """
    def __init__(self, config_path: str = "config.json"):
        with open(config_path) as f:
            cfg = json.load(f)
        jq_cfg = cfg.get("joinquant_data", {})
        # 认证
        username = jq_cfg.get("username") or os.getenv("JQ_USERNAME")
        password = jq_cfg.get("password") or os.getenv("JQ_PASSWORD")
        if username and password:
            JoinQuantAuth.authenticate(username, password)
        self.cache_dir = jq_cfg.get("cache_dir", "./data/jq_cache")
        self.cache_ttl_hours = jq_cfg.get("cache_ttl_hours", 24)
        os.makedirs(self.cache_dir, exist_ok=True)

    def _cache_key(self, func_name: str, **kwargs) -> str:
        """生成缓存键"""
        param_str = "_".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
        return f"{func_name}_{param_str}.pkl"

    def _load_cache(self, cache_key: str) -> Optional[pd.DataFrame]:
        """加载本地缓存"""
        path = os.path.join(self.cache_dir, cache_key)
        if not os.path.exists(path):
            return None
        modified = datetime.fromtimestamp(os.path.getmtime(path))
        if (datetime.now() - modified).total_seconds() > self.cache_ttl_hours * 3600:
            return None
        try:
            return pd.read_pickle(path)
        except Exception:
            return None

    def _save_cache(self, cache_key: str, data: pd.DataFrame):
        """保存本地缓存"""
        path = os.path.join(self.cache_dir, cache_key)
        try:
            data.to_pickle(path)
        except Exception:
            pass

    # ── 基本面数据 ──
    def get_fundamentals(self, stock_codes: List[str], date: str = None) -> pd.DataFrame:
        """
        获取基本面数据（静态指标）
        返回: DataFrame(code, pe_ratio, pb_ratio, ps_ratio, dividend_yield, roe, roa, debt_ratio, ...)
        """
        date = date or datetime.now().strftime("%Y-%m-%d")
        cache_key = self._cache_key("fundamentals", date=date, codes=hash(tuple(sorted(stock_codes))))
        cached = self._load_cache(cache_key)
        if cached is not None:
            return cached
        jq = JoinQuantAuth.get_client()
        try:
            # 聚宽格式: 600000.XSHG / 000001.XSHE
            jq_codes = [self._to_jq_code(c) for c in stock_codes]
            q = jq.query(
                jq.valuation.code,
                jq.valuation.pe_ratio,
                jq.valuation.pb_ratio,
                jq.valuation.ps_ratio,
                jq.valuation.dividend_ratio,
                jq.valuation.market_cap,
                jq.indicator.roe,
                jq.indicator.roa,
                jq.indicator.gross_profit_margin,
                jq.indicator.net_profit_margin,
                jq.balance.total_assets,
                jq.balance.total_liability,
            ).filter(
                jq.valuation.code.in_(jq_codes)
            )
            df = jq.get_fundamentals(q, date=date)
            if not df.empty:
                df["code"] = df["code"].apply(self._from_jq_code)
                self._save_cache(cache_key, df)
            return df
        except Exception as e:
            logger.error(f"获取基本面数据失败: {e}")
            return pd.DataFrame()

    def get_factors(self, stock_codes: List[str], factor_names: List[str], date: str = None) -> pd.DataFrame:
        """
        获取因子数据（Alpha101因子库）
        factor_names: ["alpha001", "momentum_1m", "value_ep", "quality_roe", ...]
        返回: DataFrame(code, factor1, factor2, ...)
        """
        date = date or datetime.now().strftime("%Y-%m-%d")
        jq = JoinQuantAuth.get_client()
        try:
            jq_codes = [self._to_jq_code(c) for c in stock_codes]
            factor_data = {}
            for fname in factor_names:
                try:
                    vals = jq.get_factor_values(
                        securities=jq_codes,
                        factors=fname,
                        start_date=date,
                        end_date=date
                    )
                    if vals:
                        factor_data[fname] = {
                            self._from_jq_code(k): v
                            for k, v in vals.get(fname, {}).get(date, {}).items()
                        }
                except Exception:
                    pass
            result = pd.DataFrame(factor_data)
            result.index = [self._from_jq_code(c) if "." in str(c) else c for c in result.index]
            result.index.name = "code"
            result.reset_index(inplace=True)
            return result
        except Exception as e:
            logger.error(f"获取因子数据失败: {e}")
            return pd.DataFrame()

    def get_industry_classification(self, stock_codes: List[str], level: str = "sw_l1") -> Dict[str, str]:
        """
        获取行业分类
        level: sw_l1(申万一级), sw_l2(申万二级), cs_l1(中信一级)
        返回: {stock_code: industry_name}
        """
        jq = JoinQuantAuth.get_client()
        try:
            jq_codes = [self._to_jq_code(c) for c in stock_codes]
            industry_map = {}
            for code in jq_codes:
                try:
                    industry = jq.get_industry(security=code, date=datetime.now().strftime("%Y-%m-%d"))
                    if level in industry:
                        industry_map[self._from_jq_code(code)] = industry[level]["industry_name"]
                except Exception:
                    pass
            return industry_map
        except Exception as e:
            logger.error(f"获取行业分类失败: {e}")
            return {}

    def get_institutional_holdings(self, stock_code: str, quarter: str = None) -> pd.DataFrame:
        """
        获取机构持仓（基金重仓）
        quarter: "2024q3" 格式，默认最新季度
        返回: DataFrame(fund_name, holding_ratio, change_ratio, ...)
        """
        jq = JoinQuantAuth.get_client()
        try:
            jq_code = self._to_jq_code(stock_code)
            date = quarter or datetime.now().strftime("%Y-%m-%d")
            df = jq.get_top_holdings_by_security(security=jq_code, date=date)
            return df if not df.empty else pd.DataFrame()
        except Exception as e:
            logger.warning(f"获取机构持仓失败 {stock_code}: {e}")
            return pd.DataFrame()

    def get_dividend_history(self, stock_code: str, years: int = 5) -> pd.DataFrame:
        """
        获取分红历史（用于投研报告基本面分析）
        返回: DataFrame(ex_date, dividend_per_share, bonus_per_share)
        """
        jq = JoinQuantAuth.get_client()
        start_date = (datetime.now() - timedelta(days=years * 365)).strftime("%Y-%m-%d")
        try:
            jq_code = self._to_jq_code(stock_code)
            df = jq.get_extras("is_st", [jq_code], start_date=start_date)
            divs = jq.get_all_securities(types=["stock"]).loc[jq_code] if jq_code in jq.get_all_securities().index else pd.Series()
            return pd.DataFrame()  # 简化实现，实际使用jq.get_price_for_dates等
        except Exception as e:
            logger.warning(f"获取分红历史失败 {stock_code}: {e}")
            return pd.DataFrame()

    # ── 代码格式转换工具 ──
    @staticmethod
    def _to_jq_code(code: str) -> str:
        """A股代码 → 聚宽格式 (600000 → 600000.XSHG, 000001 → 000001.XSHE)"""
        if "." in code:
            return code  # 已是聚宽格式
        code = code.strip()
        if code.startswith(("6", "5")):
            return f"{code}.XSHG"
        else:
            return f"{code}.XSHE"

    @staticmethod
    def _from_jq_code(code: str) -> str:
        """聚宽格式 → A股代码 (600000.XSHG → 600000)"""
        return code.split(".")[0] if "." in code else code


class UnifiedDataLayer:
    """
    统一数据层：融合 AkShare + Tushare + Baostock + JoinQuant
    V6.0核心：单一接口访问所有数据源，自动降级
    """
    def __init__(self, config_path: str = "config.json"):
        self.jq = JoinQuantDataGateway(config_path)
        # V5.0现有数据源（从data_gateway.py复用）
        self._legacy_available = self._check_legacy()

    def _check_legacy(self) -> bool:
        """检查V5.0数据网关是否可用"""
        try:
            from data_gateway import DataGateway
            self.legacy = DataGateway()
            return True
        except ImportError:
            logger.warning("data_gateway.py不可用，仅使用聚宽数据")
            return False

    def enrich_stock_data(self, stock_codes: List[str], date: str = None) -> pd.DataFrame:
        """
        获取增强型股票数据（行情 + 基本面 + 因子）
        返回: 合并后的综合DataFrame
        """
        date = date or datetime.now().strftime("%Y-%m-%d")
        # 基本面数据（来自聚宽）
        fundamentals = self.jq.get_fundamentals(stock_codes, date)
        # 行业分类（来自聚宽）
        industry = self.jq.get_industry_classification(stock_codes)
        # 整合
        if not fundamentals.empty and "code" in fundamentals.columns:
            fundamentals["industry"] = fundamentals["code"].map(industry)
            return fundamentals
        # 降级：返回空DataFrame含必要字段
        return pd.DataFrame({"code": stock_codes, "industry": [industry.get(c, "未知") for c in stock_codes]})
