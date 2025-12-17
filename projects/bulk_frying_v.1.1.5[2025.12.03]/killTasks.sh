#!/bin/bash

echo "Terminating the bulk_frying process..."

# Find the process ID (PID) by looking for lines containing both "run.py" and "bulk_frying"
# This is more robust and avoids issues with absolute/relative paths.
# The `grep -v grep` excludes the grep command itself from the process list.
PID=$(ps -ef | grep run.py | grep bulk_frying | grep -v grep | awk '{print $2}')

# Check if a PID was found
if [ -z "$PID" ]; then
  echo "The process 'run.py --project=bulk_frying' is not running."
else
  # Kill the process
  kill -9 $PID
  echo "Process with PID $PID has been terminated."
fi