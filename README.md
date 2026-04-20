# Vertex Handshake

FoxMQ warm-up submission for the Vertex Swarm Challenge 2026.

## What It Demonstrates

This project runs two Python agents against a local FoxMQ broker and shows:

- agent discovery over FoxMQ
- heartbeats flowing in both directions
- retained shared JSON state with `peer_id`, `last_seen_ms`, `role`, and `status`
- mirrored role changes across peers
- stale-peer detection after a simulated failure
- automatic reconnection and state recovery after restart

## Project Structure

```text
.
├── README.md
├── requirements.txt
├── scripts/
│   ├── run_warmup.sh
│   └── setup_foxmq.sh
└── warmup/
    ├── agent.py
    └── state.py
```

## Requirements

- Python 3.11+ recommended
- local FoxMQ broker
- `paho-mqtt`

## Setup

Install Python dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Download and configure FoxMQ:

```bash
bash scripts/setup_foxmq.sh
```

## Run The Demo

Start FoxMQ in one terminal:

```bash
./foxmq run --secret-key-file=foxmq.d/key_0.pem
```

Run the warm-up flow in a second terminal:

```bash
bash scripts/run_warmup.sh
```

The script will:

1. start `agent-a`
2. start `agent-b`
3. let them exchange heartbeats and retained state
4. change `agent-a` to role `scout`
5. terminate `agent-a` for ten seconds
6. restart `agent-a` and resume synchronization

## Record A Submission Video

Start recording in a second terminal:

```bash
asciinema rec warmup.cast
bash scripts/run_warmup.sh
```

## Manual Run

If you want to start the agents manually:

```bash
python3 warmup/agent.py --agent-id agent-a --peer-id agent-b --host 127.0.0.1 --port 1883 --username swarm --password swarm123
```

```bash
python3 warmup/agent.py --agent-id agent-b --peer-id agent-a --host 127.0.0.1 --port 1883 --username swarm --password swarm123
```

## Notes

- local-only files such as `codex.md`, `refs/`, `foxmq`, and `foxmq.d/` are intentionally ignored
- the demo uses retained MQTT state topics so reconnecting agents can recover context immediately
- the watchdog marks peers as stale when heartbeats stop for long enough
