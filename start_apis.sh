#!/bin/sh
set -e

echo "Starting ACC API on port $API_acc_port"
python api_acc_test.py &

echo "Starting KS API on port $API_ks_port"
python api_ks_test.py &

echo "Starting LRT API on port $API_lrt_port"
python api_lrt_test.py &

# Wait for any process to exit
wait
