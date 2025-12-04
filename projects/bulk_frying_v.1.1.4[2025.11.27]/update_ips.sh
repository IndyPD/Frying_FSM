#!/bin/bash

echo "IP 주소를 찾는 중..."

# IP 주소 찾기
CURRENT_IP=$(ip -4 addr | grep 'inet' | grep '192.168.' | awk '{print $2}' | cut -d'/' -f1 | head -n 1)

if [ -z "$CURRENT_IP" ]; then
    echo "오류: 192.168.x.x 패턴과 일치하는 IP 주소를 찾을 수 없습니다. 스크립트를 종료합니다."
    exit 1
fi

echo "발견된 IP 주소: $CURRENT_IP"

# 파일 경로
APP_CONFIG_PATH="configs/app_config.json"
CONFIGS_PATH="configs/configs.json"
DIO_CONFIG_PATH="configs/dio_config.json"

# IP 주소 업데이트 함수 (Python 사용)
update_ip() {
    local file_path=$1
    local key_path_str=$2 # "key" 또는 "parent.child" 형식

    if [ ! -f "$file_path" ]; then
        echo "경고: $file_path 경로에 설정 파일이 없습니다. 건너뜁니다."
        return
    fi

    python3 -c "
import json, sys

file_path = '$file_path'
key_path_str = '$key_path_str'
key_path = key_path_str.split('.')
new_ip = '$CURRENT_IP'

try:
    # Try to read with utf-8-sig first to handle potential BOM
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            data = json.load(f)
    except:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

    d = data
    for key in key_path[:-1]:
        d = d[key]
    
    final_key = key_path[-1]
    if final_key in d:
        d[final_key] = new_ip
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        
        print(f\"성공: '{file_path}' 파일의 '{key_path_str}' 값을 '{new_ip}'(으)로 업데이트 했습니다.\")
    else:
        print(f\"경고: '{file_path}' 파일에 키 '{key_path_str}'가 없습니다.\")

except json.JSONDecodeError as e:
    print(f\"오류: '{file_path}' 파일이 올바른 JSON 형식이 아닙니다. {e}\")
except KeyError:
    print(f\"오류: '{file_path}' 파일에서 키 경로 '{key_path_str}'를 찾을 수 없습니다.\")
except Exception as e:
    print(f'오류 발생: {e}')
"
}

echo "\n설정 파일을 업데이트하는 중..."

update_ip "$APP_CONFIG_PATH" "server.address"
update_ip "$CONFIGS_PATH" "robot_ip"
update_ip "$DIO_CONFIG_PATH" "server.address"

echo "\n업데이트 완료"

# 최종 확인 단계
echo
echo "--- 변경 사항 확인 --- "
echo "[정보] '$APP_CONFIG_PATH' 파일 확인 중:"
grep --color=always -A 1 '"server"' "$APP_CONFIG_PATH"
echo
echo "[정보] '$CONFIGS_PATH' 파일 확인 중:"
grep --color=always '"robot_ip"' "$CONFIGS_PATH"
echo
echo "[정보] '$DIO_CONFIG_PATH' 파일 확인 중:"
grep --color=always -A 1 '"server"' "$DIO_CONFIG_PATH"
echo

