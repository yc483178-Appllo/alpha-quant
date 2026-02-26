#!/bin/bash
# Alpha Quant 启动脚本

source quant_env/bin/activate

case "$1" in
    test)
        python3 alpha.py test
        ;;
    premarket)
        python3 alpha.py premarket
        ;;
    intraday)
        python3 alpha.py intraday
        ;;
    closing)
        python3 alpha.py closing
        ;;
    *)
        echo "使用方法:"
        echo "  ./start_alpha.sh test      # 测试连接"
        echo "  ./start_alpha.sh premarket # 盘前分析"
        echo "  ./start_alpha.sh intraday  # 盘中监控"
        echo "  ./start_alpha.sh closing   # 收盘复盘"
        ;;
esac
