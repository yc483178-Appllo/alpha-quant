# trade_calendar.py --- 交易日判断工具
# 解决节假日、休市日的任务调度问题

import akshare as ak
import json
import os
from datetime import datetime, timedelta
from typing import List, Optional
from loguru import logger

class TradeCalendar:
    """A股交易日历管理器 - 支持多数据源和智能缓存"""

    def __init__(self, cache_file: str = None, data_source: str = "auto"):
        """
        初始化交易日历
        
        Args:
            cache_file: 缓存文件路径，默认使用项目目录下的 cache/trade_calendar.json
            data_source: 数据源，可选 "auto", "akshare", "tushare", "ths"
        """
        if cache_file is None:
            # 默认缓存到项目 cache 目录
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            cache_dir = os.path.join(base_dir, "cache")
            os.makedirs(cache_dir, exist_ok=True)
            cache_file = os.path.join(cache_dir, "trade_calendar.json")
        
        self.cache_file = cache_file
        self.data_source = data_source
        self.trade_dates = set()
        self._cache_metadata = {}
        self._load()

    def _load(self):
        """加载交易日历（优先缓存，次选在线获取）"""
        cache_valid = False
        
        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                cached = json.load(f)
                cache_year = cached.get("year")
                cache_version = cached.get("version", 1)
                current_year = datetime.now().year
                
                # 缓存当年数据，或者上一年的数据在1月份仍然有效
                if cache_year == current_year or (cache_year == current_year - 1 and datetime.now().month == 1):
                    self.trade_dates = set(cached["dates"])
                    self._cache_metadata = cached.get("metadata", {})
                    cache_valid = True
                    logger.info(f"✅ 交易日历缓存加载成功，共 {len(self.trade_dates)} 天 (来源: {cached.get('source', 'unknown')})")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.debug(f"缓存加载失败: {e}")

        if not cache_valid:
            logger.info("缓存无效或不存在，从在线获取...")
            self._refresh()

    def _refresh(self):
        """从在线数据源获取交易日历，支持多源自动切换"""
        errors = []
        
        # 按优先级尝试不同数据源
        sources = []
        if self.data_source == "auto":
            sources = ["tushare", "akshare"]
        else:
            sources = [self.data_source]
        
        for source in sources:
            try:
                if source == "tushare":
                    self._fetch_from_tushare()
                    return
                elif source == "akshare":
                    self._fetch_from_akshare()
                    return
                elif source == "ths":
                    self._fetch_from_ths()
                    return
            except Exception as e:
                errors.append(f"{source}: {e}")
                logger.warning(f"⚠️ {source} 获取失败: {e}")
        
        # 所有源都失败
        logger.error(f"❌ 所有数据源均失败: {'; '.join(errors)}")
        # 如果之前有缓存，继续使用旧缓存
        if not self.trade_dates:
            raise Exception(f"无法获取交易日历: {'; '.join(errors)}")

    def _fetch_from_akshare(self):
        """从AkShare获取交易日历"""
        df = ak.tool_trade_date_hist_sina()
        self.trade_dates = set(df["trade_date"].astype(str).tolist())
        self._save_cache("akshare")
        logger.info(f"✅ AkShare交易日历获取成功，共 {len(self.trade_dates)} 天")

    def _fetch_from_tushare(self):
        """从Tushare获取交易日历"""
        try:
            import tushare as ts
            from dotenv import load_dotenv
            load_dotenv()
            
            pro = ts.pro_api(os.getenv("TUSHARE_TOKEN"))
            # 获取当年及前后各一年的数据
            current_year = datetime.now().year
            start_date = f"{current_year - 1}0101"
            end_date = f"{current_year + 1}1231"
            
            df = pro.trade_cal(exchange='SSE', start_date=start_date, end_date=end_date)
            df = df[df['is_open'] == 1]
            # Tushare 返回的日期格式是 YYYYMMDD，转换为 YYYY-MM-DD
            self.trade_dates = set(df['cal_date'].apply(lambda x: f"{x[:4]}-{x[4:6]}-{x[6:]}").tolist())
            self._save_cache("tushare")
            logger.info(f"✅ Tushare交易日历获取成功，共 {len(self.trade_dates)} 天")
        except ImportError:
            raise Exception("Tushare未安装")

    def _fetch_from_ths(self):
        """从同花顺SDK获取交易日历"""
        try:
            import iFinDPy
            # 尝试登录
            result = iFinDPy.THS_iFinDLogin(
                os.getenv("THS_ACCOUNT", ""),
                os.getenv("THS_PASSWORD", "")
            )
            if result != 0:
                raise Exception("同花顺登录失败")
            
            # 获取交易日历
            result = iFinDPy.THS_DateQuery('SSE', 'trade', '2024-01-01', '2026-12-31')
            if result.get('errorcode') == 0:
                dates = result.get('tables', [{}])[0].get('table', {}).get('date', [])
                self.trade_dates = set(dates)
                self._save_cache("ths")
                logger.info(f"✅ 同花顺交易日历获取成功，共 {len(self.trade_dates)} 天")
            else:
                raise Exception(result.get('errmsg', '未知错误'))
        except ImportError:
            raise Exception("iFinDPy未安装")

    def _save_cache(self, source: str):
        """保存缓存到文件"""
        cache_data = {
            "year": datetime.now().year,
            "version": 2,
            "source": source,
            "updated_at": datetime.now().isoformat(),
            "dates": sorted(list(self.trade_dates)),
            "metadata": {
                "total_days": len(self.trade_dates),
                "date_range": {
                    "start": min(self.trade_dates) if self.trade_dates else None,
                    "end": max(self.trade_dates) if self.trade_dates else None
                }
            }
        }
        
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)

    def is_trade_date(self, date: Optional[str] = None) -> bool:
        """
        判断是否为交易日
        
        Args:
            date: 日期字符串(YYYY-MM-DD)，默认今天
            
        Returns:
            是否为交易日
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        return date in self.trade_dates

    def is_trade_time(self) -> bool:
        """
        判断当前是否为交易时间（A股）
        
        Returns:
            是否在 9:30-11:30 或 13:00-15:00 的交易时段内
        """
        if not self.is_trade_date():
            return False
        
        now = datetime.now()
        time_str = now.strftime("%H:%M")
        
        # 上午 9:30-11:30，下午 13:00-15:00
        morning_start, morning_end = "09:30", "11:30"
        afternoon_start, afternoon_end = "13:00", "15:00"
        
        return (morning_start <= time_str <= morning_end) or (afternoon_start <= time_str <= afternoon_end)

    def next_trade_date(self, date: Optional[datetime] = None, n: int = 1) -> Optional[str]:
        """
        获取第n个下一个交易日
        
        Args:
            date: 起始日期，默认今天
            n: 第几个交易日，默认1（下一个）
            
        Returns:
            交易日日期字符串(YYYY-MM-DD)
        """
        if date is None:
            date = datetime.now()
        elif isinstance(date, str):
            date = datetime.strptime(date, "%Y-%m-%d")

        count = 0
        for i in range(1, 30):  # 最多往后找30天
            next_d = (date + timedelta(days=i)).strftime("%Y-%m-%d")
            if next_d in self.trade_dates:
                count += 1
                if count >= n:
                    return next_d
        return None

    def prev_trade_date(self, date: Optional[datetime] = None, n: int = 1) -> Optional[str]:
        """
        获取第n个上一个交易日
        
        Args:
            date: 起始日期，默认今天
            n: 第几个交易日，默认1（上一个）
            
        Returns:
            交易日日期字符串(YYYY-MM-DD)
        """
        if date is None:
            date = datetime.now()
        elif isinstance(date, str):
            date = datetime.strptime(date, "%Y-%m-%d")

        count = 0
        for i in range(1, 30):  # 最多往前找30天
            prev_d = (date - timedelta(days=i)).strftime("%Y-%m-%d")
            if prev_d in self.trade_dates:
                count += 1
                if count >= n:
                    return prev_d
        return None

    def trade_dates_between(self, start: str, end: str) -> List[str]:
        """
        获取区间内的所有交易日
        
        Args:
            start: 开始日期(YYYY-MM-DD)
            end: 结束日期(YYYY-MM-DD)
            
        Returns:
            交易日列表
        """
        return sorted([d for d in self.trade_dates if start <= d <= end])

    def get_trade_dates(self, days: int = 20, end_date: Optional[str] = None) -> List[str]:
        """
        获取最近N个交易日
        
        Args:
            days: 交易日数量，默认20
            end_date: 结束日期，默认今天
            
        Returns:
            交易日列表（倒序，从近到远）
        """
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")
        
        # 获取所有小于等于end_date的交易日
        valid_dates = sorted([d for d in self.trade_dates if d <= end_date], reverse=True)
        return valid_dates[:days]

    def days_between(self, start: str, end: str) -> int:
        """
        计算两个日期之间的交易日数量
        
        Args:
            start: 开始日期(YYYY-MM-DD)
            end: 结束日期(YYYY-MM-DD)
            
        Returns:
            交易日数量
        """
        return len(self.trade_dates_between(start, end))

    def should_run_task(self, task_type: str = "daily") -> bool:
        """
        智能判断是否应该执行任务
        
        Args:
            task_type: 任务类型，可选 "daily"(每日), "intraday"(盘中), "pre_market"(盘前)
            
        Returns:
            是否应该执行
        """
        if not self.is_trade_date():
            return False
        
        if task_type == "intraday":
            return self.is_trade_time()
        elif task_type == "pre_market":
            now = datetime.now()
            time_str = now.strftime("%H:%M")
            # 盘前任务：8:00-9:30
            return "08:00" <= time_str < "09:30"
        elif task_type == "post_market":
            now = datetime.now()
            time_str = now.strftime("%H:%M")
            # 盘后任务：15:00-20:00
            return "15:00" <= time_str < "20:00"
        
        return True

    def get_market_phase(self) -> str:
        """
        获取当前市场阶段
        
        Returns:
            市场阶段描述
        """
        if not self.is_trade_date():
            return "休市"
        
        now = datetime.now()
        time_str = now.strftime("%H:%M")
        weekday = now.weekday()
        
        # 周末
        if weekday >= 5:
            return "周末休市"
        
        # 交易时段
        if "09:30" <= time_str <= "11:30":
            return "上午交易"
        elif "11:30" < time_str < "13:00":
            return "午间休市"
        elif "13:00" <= time_str <= "15:00":
            return "下午交易"
        elif "15:00" < time_str:
            return "盘后"
        elif "09:15" <= time_str < "09:30":
            return "集合竞价"
        else:
            return "盘前"

    def __repr__(self) -> str:
        return f"TradeCalendar(dates={len(self.trade_dates)}, source={self._cache_metadata.get('source', 'unknown')})"


# 全局单例实例
calendar = None

def get_calendar() -> TradeCalendar:
    """获取全局交易日历实例（单例模式）"""
    global calendar
    if calendar is None:
        calendar = TradeCalendar()
    return calendar


# 便捷函数
def is_trade_date(date: Optional[str] = None) -> bool:
    """判断是否为交易日"""
    return get_calendar().is_trade_date(date)

def is_trade_time() -> bool:
    """判断当前是否为交易时间"""
    return get_calendar().is_trade_time()

def next_trade_date(date: Optional[datetime] = None, n: int = 1) -> Optional[str]:
    """获取第n个下一个交易日"""
    return get_calendar().next_trade_date(date, n)

def prev_trade_date(date: Optional[datetime] = None, n: int = 1) -> Optional[str]:
    """获取第n个上一个交易日"""
    return get_calendar().prev_trade_date(date, n)


# 使用示例
if __name__ == "__main__":
    cal = TradeCalendar()
    today = datetime.now().strftime("%Y-%m-%d")
    
    print("=" * 50)
    print(f"📅 交易日历信息 ({today})")
    print("=" * 50)
    print(f"是否交易日: {cal.is_trade_date()}")
    print(f"当前市场阶段: {cal.get_market_phase()}")
    print(f"是否交易时间: {cal.is_trade_time()}")
    print(f"下一个交易日: {cal.next_trade_date()}")
    print(f"上一个交易日: {cal.prev_trade_date()}")
    print(f"最近5个交易日: {cal.get_trade_dates(5)}")
    print("=" * 50)
    
    # 任务调度示例
    print("\n📋 任务调度检查:")
    print(f"  每日任务: {'✅ 执行' if cal.should_run_task('daily') else '⏸️ 跳过'}")
    print(f"  盘中任务: {'✅ 执行' if cal.should_run_task('intraday') else '⏸️ 跳过'}")
    print(f"  盘前任务: {'✅ 执行' if cal.should_run_task('pre_market') else '⏸️ 跳过'}")
    print(f"  盘后任务: {'✅ 执行' if cal.should_run_task('post_market') else '⏸️ 跳过'}")
