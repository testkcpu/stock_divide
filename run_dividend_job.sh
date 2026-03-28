#!/bin/bash
# 高股息分析定时任务脚本
# 每天09:00和16:00执行

# 设置工作目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 设置Python环境（使用系统默认python3）
PYTHON_CMD="python3"

# 日志文件
LOG_FILE="/tmp/dividend_job_$(date +%Y%m%d_%H%M%S).log"

echo "========================================" >> "$LOG_FILE"
echo "股息分析任务开始: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
echo "工作目录: $SCRIPT_DIR" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

# 检查Python环境
if ! command -v $PYTHON_CMD &> /dev/null; then
    echo "错误: Python3 未安装" >> "$LOG_FILE"
    exit 1
fi

# 检查依赖
echo "检查依赖..." >> "$LOG_FILE"
$PYTHON_CMD -c "import requests, matplotlib, numpy" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "安装依赖..." >> "$LOG_FILE"
    pip3 install requests matplotlib numpy -q >> "$LOG_FILE" 2>&1
fi

# 执行发送脚本
echo "执行股息分析并发送..." >> "$LOG_FILE"
$PYTHON_CMD "$SCRIPT_DIR/send_wechat.py" >> "$LOG_FILE" 2>&1

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ 任务执行成功" >> "$LOG_FILE"
else
    echo "❌ 任务执行失败，退出码: $EXIT_CODE" >> "$LOG_FILE"
fi

echo "任务结束: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

# 清理7天前的日志
find /tmp -name "dividend_job_*.log" -mtime +7 -delete 2>/dev/null

exit $EXIT_CODE
