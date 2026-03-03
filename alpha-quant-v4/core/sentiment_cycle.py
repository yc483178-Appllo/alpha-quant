# sentiment_cycle.py --- 情绪周期四阶段模型
# 冰点 → 回暖 → 高潮 → 退潮 → 冰点（循环）

import akshare as ak
from loguru import logger

class SentimentCycleModel:
    """
    A股情绪周期四阶段模型

    阶段一 · 冰点期：涨停<20家，跌停>30家，连板断裂
    阶段二 · 回暖期：涨停30-50家，出现2-3连板，资金开始活跃
    阶段三 · 高潮期：涨停>60家，高标连板加速，市场亢奋
    阶段四 · 退潮期：高标断板，跟风大面，涨停开始缩减
    """

    def detect_phase(self):
        """检测当前情绪周期阶段"""
        try:
            # 获取涨停池
            zt_df = ak.stock_zt_pool_em(date="")
            zt_count = len(zt_df) if not zt_df.empty else 0

            # 获取跌停池
            try:
                dt_df = ak.stock_zt_pool_dtgc_em(date="")
                dt_count = len(dt_df) if not dt_df.empty else 0
            except:
                dt_count = 0

            # 连板统计
            if not zt_df.empty and "连板数" in zt_df.columns:
                max_board = int(zt_df["连板数"].max())
                board_2plus = len(zt_df[zt_df["连板数"] >= 2])
            else:
                max_board = 0
                board_2plus = 0

            # 涨跌比
            spot_df = ak.stock_zh_a_spot_em()
            ups = len(spot_df[spot_df["涨跌幅"] > 0])
            downs = len(spot_df[spot_df["涨跌幅"] < 0])

            # 判断阶段
            if zt_count < 20 and dt_count > 30:
                phase = "冰点期"
                phase_id = 1
                strategy_advice = "空仓观望，等待情绪修复信号"
                color = "🔵"
            elif 30 <= zt_count <= 55 and max_board >= 2 and ups > downs:
                phase = "回暖期"
                phase_id = 2
                strategy_advice = "轻仓试水，关注率先启动的方向"
                color = "🟢"
            elif zt_count > 55 and max_board >= 4:
                phase = "高潮期"
                phase_id = 3
                strategy_advice = "适度参与，但警惕高位风险，不追涨"
                color = "🔴"
            elif zt_count > 30 and dt_count > 15 and max_board < 3:
                phase = "退潮期"
                phase_id = 4
                strategy_advice = "减仓防守，避免追高，等待下一轮冰点"
                color = "🟠"
            else:
                phase = "过渡期"
                phase_id = 0
                strategy_advice = "方向不明，保持原有仓位不动"
                color = "⚪"

            result = {
                "phase": phase,
                "phase_id": phase_id,
                "color": color,
                "zt_count": zt_count,
                "dt_count": dt_count,
                "max_board": max_board,
                "board_2plus": board_2plus,
                "ups_downs_ratio": f"{ups}:{downs}",
                "strategy_advice": strategy_advice,
            }
            logger.info(f"情绪周期: {color} {phase} | 涨停{zt_count}家 | 最高{max_board}板")
            return result

        except Exception as e:
            logger.error(f"情绪周期检测失败: {e}")
            return {"phase": "未知", "phase_id": -1, "strategy_advice": "数据异常，暂停操作"}

if __name__ == "__main__":
    model = SentimentCycleModel()
    result = model.detect_phase()
    print(f"\n{result['color']} 当前情绪周期: {result['phase']}")
    print(f"涨停: {result['zt_count']}家 | 跌停: {result.get('dt_count', 'N/A')}家")
    print(f"最高连板: {result['max_board']}板")
    print(f"策略建议: {result['strategy_advice']}")
