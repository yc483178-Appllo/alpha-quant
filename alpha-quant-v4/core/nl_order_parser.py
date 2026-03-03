# nl_order_parser.py --- 自然语言下单解析器
# 将用户的自然语言指令转换为标准化交易信号

import re
import akshare as ak
from loguru import logger

class NLOrderParser:
    """
    自然语言交易指令解析器

    支持的指令格式：
    "买入5万块招商银行"
    "卖掉一半平安银行"
    "清仓所有银行股"
    "600036买入1000股，限价35元"
    "帮我在35.5以下买入招商银行，金额5万"
    """

    # 股票名称 → 代码映射缓存
    _name_cache = {}

    def __init__(self):
        self._load_stock_names()

    def _load_stock_names(self):
        """加载A股名称代码映射"""
        try:
            df = ak.stock_zh_a_spot_em()
            self._name_cache = dict(zip(df["名称"], df["代码"]))
            self._code_to_name = dict(zip(df["代码"], df["名称"]))
            self._price_cache = dict(zip(df["代码"], df["最新价"]))
            logger.info(f"股票名称库加载完成: {len(self._name_cache)} 只")
        except Exception as e:
            logger.error(f"名称库加载失败: {e}")

    def parse(self, text):
        """
        解析自然语言交易指令

        返回: dict 标准化交易信号，或 None（解析失败）
        """
        text = text.strip()
        logger.info(f"解析指令: {text}")

        # 判断买/卖方向
        if any(kw in text for kw in ["买入", "买", "建仓", "加仓"]):
            action = "buy"
        elif any(kw in text for kw in ["卖出", "卖", "清仓", "减仓", "卖掉"]):
            action = "sell"
        else:
            return {"error": "无法判断买卖方向，请包含"买"或"卖"关键词"}

        # 提取股票代码或名称
        code = None
        name = None

        # 尝试匹配6位数字代码
        code_match = re.search(r"(\d{6})", text)
        if code_match:
            code = code_match.group(1)
            name = self._code_to_name.get(code, "未知")
        else:
            # 尝试匹配股票名称
            for stock_name, stock_code in self._name_cache.items():
                if stock_name in text:
                    code = stock_code
                    name = stock_name
                    break

        if not code:
            return {"error": "未识别到股票代码或名称"}

        # 提取金额
        amount_money = None
        amount_shares = None

        money_match = re.search(r"(\d+(?:\.\d+)?)\s*[万w]", text)
        if money_match:
            amount_money = float(money_match.group(1)) * 10000

        shares_match = re.search(r"(\d+)\s*股", text)
        if shares_match:
            amount_shares = int(shares_match.group(1))

        # "一半"处理
        if "一半" in text or "50%" in text:
            amount_shares = "half"

        # "清仓" / "全部" 处理
        if "清仓" in text or "全部" in text:
            amount_shares = "all"

        # 提取限价
        limit_price = None
        price_match = re.search(r"(?:限价|价格|在)\s*(\d+(?:\.\d+)?)", text)
        if price_match:
            limit_price = float(price_match.group(1))

        # 计算股数
        current_price = float(self._price_cache.get(code, 0))
        if amount_money and current_price > 0 and amount_shares is None:
            amount_shares = int(amount_money / current_price / 100) * 100

        signal = {
            "action": action,
            "code": code,
            "name": name,
            "amount": amount_shares,
            "limit_price": limit_price or current_price,
            "current_price": current_price,
            "original_text": text,
            "parsed_at": __import__("datetime").datetime.now().isoformat()
        }

        logger.info(f"解析结果: {action.upper()} {name}({code}) | 数量: {amount_shares} | 价格: {limit_price or '市价'}")
        return signal

# 使用示例
if __name__ == "__main__":
    parser = NLOrderParser()
    tests = [
        "买入5万块招商银行",
        "卖掉一半平安银行",
        "600036买入1000股，限价35元",
        "清仓所有持仓",
        "帮我在12块以下买入平安银行，金额3万",
    ]
    for t in tests:
        print(f"\n指令: {t}")
        result = parser.parse(t)
        for k, v in result.items():
            print(f"  {k}: {v}")
