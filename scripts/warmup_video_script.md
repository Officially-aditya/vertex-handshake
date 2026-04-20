# Warm-Up Video Script

Use this while recording the FoxMQ warm-up demo.

## Before You Start

In terminal 1:

```bash
./foxmq run --secret-key-file=foxmq.d/key_0.pem
```

In terminal 2:

```bash
asciinema rec warmup.cast
bash scripts/run_warmup.sh
```

## Voiceover

"This is my FoxMQ warm-up submission for the Vertex Swarm Challenge 2026."

"I’m running two agents, `agent-a` and `agent-b`, against a local FoxMQ broker."

"Right now both agents are connecting, discovering each other, and syncing retained shared state over consensus-backed MQTT."

"You can see heartbeats flowing in both directions every two seconds, and each agent is tracking the peer state with `peer_id`, `last_seen_ms`, `role`, and `status`."

"Next, I trigger a role change on `agent-a` from `carrier` to `scout`."

"`agent-b` receives that state update and mirrors the role change immediately, which shows replicated state and sub-second reaction across peers."

"Now I’m simulating a failure by stopping `agent-a` for ten seconds."

"`agent-b` marks `agent-a` as stale after the disconnect, while continuing to run and publish its own heartbeat."

"Now `agent-a` is starting again and reconnecting to FoxMQ automatically."

"You can see discovery resume, the shared state recover, and both agents continue heartbeats without manual repair."

"This demonstrates the complete warm-up flow: discovery, heartbeats, replicated JSON state, mirrored role change, stale detection, and automatic recovery."

"That completes the FoxMQ warm-up demo."

## Shorter Version

If you want a faster take, read this instead:

"This is my FoxMQ warm-up for the Vertex Swarm Challenge. Two agents connect to a local FoxMQ broker, discover each other, and exchange heartbeats. Their retained shared state includes `peer_id`, `last_seen_ms`, `role`, and `status`. I trigger a role change on `agent-a`, and `agent-b` mirrors it immediately. Then I stop `agent-a`, `agent-b` marks it stale, and when `agent-a` restarts both agents reconnect and resume state sync automatically. That completes the warm-up requirements."
