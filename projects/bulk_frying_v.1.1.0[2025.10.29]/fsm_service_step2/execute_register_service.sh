# #!/bin/bash

# SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# FSM_DIR="$(dirname "$SCRIPT_DIR")"
# SERVICE_DIR="$SCRIPT_DIR"

# echo "'=========== Registering Service ============'"
# echo "Changing directory to $SERVICE_DIR"
# cd "$SERVICE_DIR" || { echo "Failed to change directory to $SERVICE_DIR"; exit 1; }
# sudo chmod 777 *
# echo "Running ./register_service.sh script."
# sudo ./register_service.sh

#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_DIR="$SCRIPT_DIR"

echo "=========== Registering Service ==========="
echo "Changing directory to $SERVICE_DIR"
cd "$SERVICE_DIR" || { echo "Failed to change directory to $SERVICE_DIR"; exit 1; }

echo "Granting permissions..."
sudo chmod 777 *

echo "Running ./register_service.sh script."
sudo ./register_service.sh