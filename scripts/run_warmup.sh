#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
FOXMQ_HOST="${FOXMQ_HOST:-127.0.0.1}"
FOXMQ_PORT="${FOXMQ_PORT:-1883}"
FOXMQ_USERNAME="${FOXMQ_USERNAME:-swarm}"
FOXMQ_PASSWORD="${FOXMQ_PASSWORD:-swarm123}"

A_PID=""
B_PID=""

cleanup() {
  if [[ -n "${A_PID}" ]]; then
    kill "${A_PID}" 2>/dev/null || true
  fi
  if [[ -n "${B_PID}" ]]; then
    kill "${B_PID}" 2>/dev/null || true
  fi
}

trap cleanup EXIT

echo "=== Starting Warm Up ==="

echo "=== Clearing retained warm-up state from prior runs ==="
"${PYTHON_BIN}" -c '
import paho.mqtt.client as mqtt
import time

host = "'"${FOXMQ_HOST}"'"
port = int("'"${FOXMQ_PORT}"'")
username = "'"${FOXMQ_USERNAME}"'"
password = "'"${FOXMQ_PASSWORD}"'"

client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, protocol=mqtt.MQTTv5)
client.username_pw_set(username, password)
client.connect(host, port, keepalive=10)
client.loop_start()
time.sleep(1)
client.publish("warmup/state/agent-a", b"", qos=1, retain=True)
client.publish("warmup/state/agent-b", b"", qos=1, retain=True)
time.sleep(1)
client.disconnect()
'

PYTHONUNBUFFERED=1 "${PYTHON_BIN}" "${ROOT_DIR}/warmup/agent.py" \
  --agent-id agent-a \
  --peer-id agent-b \
  --host "${FOXMQ_HOST}" \
  --port "${FOXMQ_PORT}" \
  --username "${FOXMQ_USERNAME}" \
  --password "${FOXMQ_PASSWORD}" &
A_PID=$!

sleep 1

PYTHONUNBUFFERED=1 "${PYTHON_BIN}" "${ROOT_DIR}/warmup/agent.py" \
  --agent-id agent-b \
  --peer-id agent-a \
  --host "${FOXMQ_HOST}" \
  --port "${FOXMQ_PORT}" \
  --username "${FOXMQ_USERNAME}" \
  --password "${FOXMQ_PASSWORD}" &
B_PID=$!

sleep 6

echo "=== Triggering role change on agent-a ==="
"${PYTHON_BIN}" -c '
import json
import time
import paho.mqtt.client as mqtt

host = "'"${FOXMQ_HOST}"'"
port = int("'"${FOXMQ_PORT}"'")
username = "'"${FOXMQ_USERNAME}"'"
password = "'"${FOXMQ_PASSWORD}"'"

payload = {
    "peer_id": "agent-a",
    "last_seen_ms": int(time.time() * 1000),
    "role": "scout",
    "status": "ready",
}

client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, protocol=mqtt.MQTTv5)
client.username_pw_set(username, password)
client.connect(host, port, keepalive=10)
client.loop_start()
time.sleep(1)
client.publish("warmup/state/agent-a", json.dumps(payload), qos=1, retain=True)
print("role change injected for agent-a")
time.sleep(1)
client.disconnect()
'

sleep 5

echo "=== Killing agent-a for 10 seconds (fault injection) ==="
kill -TERM "${A_PID}"
wait "${A_PID}" 2>/dev/null || true
A_PID=""

sleep 10

echo "=== Restarting agent-a ==="
PYTHONUNBUFFERED=1 "${PYTHON_BIN}" "${ROOT_DIR}/warmup/agent.py" \
  --agent-id agent-a \
  --peer-id agent-b \
  --host "${FOXMQ_HOST}" \
  --port "${FOXMQ_PORT}" \
  --username "${FOXMQ_USERNAME}" \
  --password "${FOXMQ_PASSWORD}" &
A_PID=$!

sleep 15

echo "=== Warm Up complete ==="
