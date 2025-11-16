#!/bin/bash

# 현재 날짜를 "YYYY-MM-DD" 형식으로 가져와서 파일 이름에 사용합니다.
LOG_FILE="ping_log_$(date +"%Y-%m-%d").txt"

# 스크립트 시작 메시지를 로그 파일에 추가합니다.
echo "--- Ping 스크립트 시작: $(date) ---" >> "$LOG_FILE"

# 무한 루프를 실행합니다.
while true
do
    # 현재 시간을 가져와서 타임스탬프 변수에 저장합니다.
    TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")

    # 8.8.8.8로 핑을 한 번 보냅니다. (-c 1: 1회, -W 1: 타임아웃 1초)
    # 결과를 $LOG_FILE에 추가하고, 타임스탬프를 함께 기록합니다.
    echo "[$TIMESTAMP] Ping 결과:" >> "$LOG_FILE"
    ping -c 1 -W 1 8.8.8.8 >> "$LOG_FILE" 2>&1

    # 가독성을 위해 빈 줄을 추가합니다.
    echo "" >> "$LOG_FILE"

    # 다음 핑까지 1초간 대기합니다.
    sleep 1
done