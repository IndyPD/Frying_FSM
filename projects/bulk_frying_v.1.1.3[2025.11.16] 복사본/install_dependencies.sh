#!/bin/bash
# offline installer: wheels first, then any local source dirs (recursive setup.py search)
# Python 3.7 오프라인 환경 대응
set -euo pipefail

INSTALLER_DIR="installer"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PIP_CMD="$PYTHON_BIN -m pip"

# 강제 재설치: FORCE_REINSTALL=1 ./install_dependencies.sh
PIP_EXTRA=""
if [[ "${FORCE_REINSTALL:-0}" == "1" ]]; then
  PIP_EXTRA="--force-reinstall"
fi

# 소스 설치 시 온라인 의존성 설치를 막기 위해 build isolation 비활성화
NO_ISOLATION="--no-build-isolation"

if [ ! -d "$INSTALLER_DIR" ]; then
  echo "Error: '$INSTALLER_DIR' not found. Put .whl or package folders under it."
  exit 1
fi

echo "[INFO] Using Python: $($PYTHON_BIN -V 2>/dev/null || true)"
echo "[INFO] Using Pip:    $($PYTHON_BIN -m pip -V 2>/dev/null || true)"
echo

shopt -s nullglob

########################################
# 1) .whl 먼저 설치
########################################
if compgen -G "$INSTALLER_DIR/*.whl" > /dev/null; then
  echo "[STEP] Installing local wheels from '$INSTALLER_DIR'..."
  WHEELS=( "$INSTALLER_DIR"/*.whl )
  $PIP_CMD install --no-index --find-links "$INSTALLER_DIR" $PIP_EXTRA "${WHEELS[@]}"
  echo "[OK] Wheel installation complete."
  echo
else
  echo "[WARN] No .whl files found in '$INSTALLER_DIR'."
fi

########################################
# 2) 재귀적으로 setup.py 찾기 → 해당 디렉터리 설치
########################################
echo "[STEP] Scanning for local source packages (setup.py) under '$INSTALLER_DIR'..."
# setup.py가 있는 디렉터리를 전부 수집(중복 제거)
mapfile -t SETUP_DIRS < <(
  find "$INSTALLER_DIR" -type f -name "setup.py" \
  | sed 's|/setup\.py$||' \
  | sort -u
)

if [ ${#SETUP_DIRS[@]} -eq 0 ]; then
  echo "[INFO] No setup.py found recursively under '$INSTALLER_DIR'."
else
  FAILED_DIRS=()
  for dir in "${SETUP_DIRS[@]}"; do
    pkg_name="$(basename "$dir")"
    echo "  -> Installing from: $dir"

    # 2-1) pip로 먼저(오프라인 + no-build-isolation)
    if $PIP_CMD install --no-index --find-links "$INSTALLER_DIR" $PIP_EXTRA $NO_ISOLATION "$dir"; then
      echo "     [OK] pip install: $pkg_name"
      continue
    fi

    echo "     [WARN] pip install failed, trying 'setup.py install' fallback..."
    if ( cd "$dir" && "$PYTHON_BIN" setup.py install ); then
      echo "     [OK] setup.py install: $pkg_name"
    else
      echo "     [ERR] install failed: $pkg_name"
      FAILED_DIRS+=("$dir")
    fi
  done

  if [ ${#FAILED_DIRS[@]} -gt 0 ]; then
    echo
    echo "[SUMMARY] Failed source installs:"
    for p in "${FAILED_DIRS[@]}"; do echo " - $p"; done
    echo "Tip: 위 패키지들은 .whl 파일을 준비해서 넣으면 빌드 없이 안정적으로 설치됩니다."
    exit 2
  fi
fi

########################################
# 3) sdist(.tar.gz/.zip) 알림
########################################
if compgen -G "$INSTALLER_DIR/*.tar.gz" > /dev/null || compgen -G "$INSTALLER_DIR/*.zip" > /dev/null; then
  echo "[NOTE] Found sdist archives (*.tar.gz / *.zip)."
  echo "      오프라인+py37에선 빌드 체인 충돌이 잦습니다. 가능하면 동일 버전의 .whl 권장."
fi

echo
echo "[DONE] Offline installation finished successfully."