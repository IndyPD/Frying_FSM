#!/bin/bash

ServiceName=frying_fsm
SERVICE_DIR="$(pwd)"
PROJECT_ROOT="$(dirname "$SERVICE_DIR")"

echo "[INFO] 프로젝트 루트: $PROJECT_ROOT"
echo "[INFO] 서비스 스크립트 위치: $SERVICE_DIR"

# 1. 모든 관련 스크립트에 실행 권한을 먼저 부여합니다.
echo "[STEP 1] 스크립트 실행 권한을 설정합니다..."
chmod +x "$PROJECT_ROOT/killTasks.sh"
chmod +x "$PROJECT_ROOT/run.sh" # 만약을 위해 권한을 줍니다.
chmod +x "$PROJECT_ROOT/update_ips.sh"
chmod +x "$SERVICE_DIR/check_robot_status.py"

# 2. 메인 서비스 스크립트를 준비하고 /etc/ 위치로 복사합니다.
echo "[STEP 2] 서비스 스크립트를 시스템에 복사합니다..."
sed "s#PROJECT_ROOT_PATH_PLACEHOLDER#$PROJECT_ROOT#" "${SERVICE_DIR}/${ServiceName}_script" > "/tmp/${ServiceName}_script_modified"
sudo cp "/tmp/${ServiceName}_script_modified" "/etc/${ServiceName}_script"
rm "/tmp/${ServiceName}_script_modified"

# 3. 서비스 실행 파일을 복사하고 권한을 설정합니다.
sudo cp "${SERVICE_DIR}/$ServiceName" /etc/init.d/
sudo chmod 775 /etc/init.d/"$ServiceName"
sudo chmod 775 /etc/"${ServiceName}_script"

# 4. 서비스를 시스템에 다시 등록하고 재시작합니다.
echo "[STEP 3] 서비스를 시스템에 등록하고 재시작합니다..."
sudo update-rc.d -f $ServiceName remove
sudo update-rc.d $ServiceName defaults
sudo service $ServiceName stop
sudo service $ServiceName start

echo "[SUCCESS] 모든 서비스 등록 절차가 완료되었습니다."