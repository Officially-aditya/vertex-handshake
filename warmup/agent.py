from __future__ import annotations

import argparse
import json
import signal
import threading
from datetime import datetime
from typing import Any

import paho.mqtt.client as mqtt

try:
    from state import SharedState, now_ms
except ImportError:
    from warmup.state import SharedState, now_ms


TOPIC_HELLO = "warmup/hello"
TOPIC_STATE = "warmup/state"
TOPIC_HEARTBEAT = "warmup/heartbeat"
CONNECT_PUBLISH_DELAY_SEC = 0.5


def log(agent_id: str, event: str, detail: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{ts}] [{agent_id}] {event:<12} {detail}", flush=True)


class WarmupAgent:
    def __init__(self, args: argparse.Namespace) -> None:
        self.agent_id = args.agent_id
        self.peer_id = args.peer_id or self._default_peer_id(args.agent_id)
        self.host = args.host
        self.port = args.port
        self.username = args.username
        self.password = args.password
        self.heartbeat_interval = args.heartbeat_interval
        self.stale_after_ms = args.stale_after_ms

        self.state = SharedState.fresh(
            peer_id=self.agent_id,
            role=args.role,
            status=args.status,
        )
        self.peers: dict[str, SharedState] = {}
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.background_started = False

        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=self.agent_id,
            protocol=mqtt.MQTTv5,
        )
        self.client.username_pw_set(self.username, self.password)
        self.client.reconnect_delay_set(min_delay=1, max_delay=5)
        self.client.will_set(
            self._state_topic(self.agent_id),
            payload=json.dumps(self._stale_payload()),
            qos=1,
            retain=True,
        )
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message

    def _default_peer_id(self, agent_id: str) -> str:
        if agent_id == "agent-a":
            return "agent-b"
        if agent_id == "agent-b":
            return "agent-a"
        raise ValueError("--peer-id is required for agent IDs other than agent-a / agent-b")

    def _hello_topic(self, agent_id: str) -> str:
        return f"{TOPIC_HELLO}/{agent_id}"

    def _state_topic(self, agent_id: str) -> str:
        return f"{TOPIC_STATE}/{agent_id}"

    def _heartbeat_topic(self, agent_id: str) -> str:
        return f"{TOPIC_HEARTBEAT}/{agent_id}"

    def _stale_payload(self) -> dict[str, Any]:
        return {
            "peer_id": self.agent_id,
            "last_seen_ms": now_ms(),
            "role": self.state.role,
            "status": "stale",
        }

    def _publish_json(self, topic: str, payload: dict[str, Any], *, retain: bool = False) -> None:
        info = self.client.publish(topic, json.dumps(payload), qos=1, retain=retain)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            log(self.agent_id, "PUBLISH_ERR", f"{topic} rc={info.rc}")

    def _publish_state(self, reason: str) -> None:
        with self.lock:
            self.state.touch()
            payload = self.state.as_dict()
        self._publish_json(self._state_topic(self.agent_id), payload, retain=True)
        log(
            self.agent_id,
            "STATE",
            f"{reason} role={payload['role']} status={payload['status']}",
        )

    def _publish_hello(self) -> None:
        payload = {
            "type": "hello",
            "from": self.agent_id,
            "peer_id": self.peer_id,
            "ts": now_ms(),
        }
        self._publish_json(self._hello_topic(self.agent_id), payload)
        log(self.agent_id, "HELLO", f"announced to {self.peer_id}")

    def _publish_connected_state(self) -> None:
        with self.lock:
            if self.state.status == "stale":
                self.state.status = "ready"
        self._publish_state("connected")

    def _ensure_background_workers(self) -> None:
        if self.background_started:
            return

        threading.Thread(target=self._heartbeat_loop, daemon=True).start()
        threading.Thread(target=self._watchdog_loop, daemon=True).start()
        self.background_started = True

    def on_connect(self, client: mqtt.Client, userdata, flags, reason_code, properties) -> None:
        if reason_code != 0:
            log(self.agent_id, "ERROR", f"connection failed rc={reason_code}")
            return

        client.subscribe(f"{TOPIC_HELLO}/+", qos=1)
        client.subscribe(f"{TOPIC_STATE}/+", qos=1)
        client.subscribe(f"{TOPIC_HEARTBEAT}/+", qos=1)
        log(self.agent_id, "CONNECTED", f"broker={self.host}:{self.port}")

        self._ensure_background_workers()
        self._publish_hello()
        threading.Timer(CONNECT_PUBLISH_DELAY_SEC, self._publish_connected_state).start()

    def on_disconnect(self, client: mqtt.Client, userdata, disconnect_flags, reason_code, properties) -> None:
        if self.stop_event.is_set():
            log(self.agent_id, "STOPPED", "clean shutdown")
            return
        log(self.agent_id, "DISCONNECTED", f"rc={reason_code}")

    def on_message(self, client: mqtt.Client, userdata, message: mqtt.MQTTMessage) -> None:
        try:
            payload = json.loads(message.payload.decode("utf-8"))
        except json.JSONDecodeError:
            log(self.agent_id, "BAD_JSON", f"topic={message.topic}")
            return

        source_id = message.topic.rsplit("/", 1)[-1]
        if message.topic.startswith(f"{TOPIC_HELLO}/"):
            self._handle_hello(source_id, payload)
            return
        if message.topic.startswith(f"{TOPIC_STATE}/"):
            self._handle_state(source_id, payload)
            return
        if message.topic.startswith(f"{TOPIC_HEARTBEAT}/"):
            self._handle_heartbeat(source_id, payload)

    def _handle_hello(self, source_id: str, payload: dict[str, Any]) -> None:
        if source_id == self.agent_id:
            return
        log(self.agent_id, "DISCOVERED", f"{source_id} via hello")

    def _handle_state(self, source_id: str, payload: dict[str, Any]) -> None:
        try:
            state = SharedState.from_payload(payload)
        except (KeyError, TypeError, ValueError):
            log(self.agent_id, "BAD_STATE", f"from={source_id}")
            return

        if source_id == self.agent_id:
            with self.lock:
                previous_role = self.state.role
                previous_status = self.state.status
                self.state = state

            if (state.role, state.status) != (previous_role, previous_status):
                log(
                    self.agent_id,
                    "SELF_SYNC",
                    f"role={state.role} status={state.status}",
                )
            return

        mirrored = False
        recovered = False
        became_stale = False
        with self.lock:
            previous = self.peers.get(source_id)
            recovered = previous is not None and previous.status == "stale" and state.status != "stale"
            became_stale = (previous is None or previous.status != "stale") and state.status == "stale"
            self.peers[source_id] = state

            if source_id == self.peer_id and state.status != "stale" and (
                self.state.role != state.role or self.state.status == "stale"
            ):
                self.state.role = state.role
                self.state.touch(status="ready")
                mirrored = True

        log(
            self.agent_id,
            "STATE_SYNC",
            f"{source_id} role={state.role} status={state.status}",
        )
        if became_stale:
            log(self.agent_id, "STALE", f"{source_id} marked stale")
        if recovered:
            log(self.agent_id, "RECOVERED", f"{source_id} state restored")
        if mirrored:
            self._publish_state("mirrored")
            log(self.agent_id, "MIRRORED", f"role -> {state.role}")

    def _handle_heartbeat(self, source_id: str, payload: dict[str, Any]) -> None:
        if source_id == self.agent_id:
            return

        recovered = False
        with self.lock:
            peer = self.peers.get(source_id)
            if peer is None:
                peer = SharedState.fresh(peer_id=source_id)
                self.peers[source_id] = peer
            recovered = peer.status == "stale"
            peer.last_seen_ms = now_ms()
            if peer.status == "stale":
                peer.status = "ready"

        log(self.agent_id, "HEARTBEAT", f"from={source_id}")
        if recovered:
            log(self.agent_id, "RECOVERED", f"{source_id} heartbeat resumed")

    def _heartbeat_loop(self) -> None:
        while not self.stop_event.wait(self.heartbeat_interval):
            with self.lock:
                if self.state.status == "stale":
                    self.state.status = "ready"
            payload = {"from": self.agent_id, "ts": now_ms()}
            self._publish_json(self._heartbeat_topic(self.agent_id), payload)
            self._publish_state("heartbeat")
            log(self.agent_id, "HEARTBEAT", "sent")

    def _watchdog_loop(self) -> None:
        while not self.stop_event.wait(1.0):
            stale_peers: list[str] = []

            with self.lock:
                for peer_id, state in self.peers.items():
                    if state.status != "stale" and state.age_ms() > self.stale_after_ms:
                        state.status = "stale"
                        stale_peers.append(peer_id)

            for peer_id in stale_peers:
                log(self.agent_id, "STALE", f"{peer_id} missed heartbeats")

    def run(self) -> None:
        log(self.agent_id, "STARTING", f"connecting to {self.host}:{self.port}")
        try:
            self.client.connect(self.host, self.port, keepalive=10)
            self.client.loop_forever()
        except KeyboardInterrupt:
            self.shutdown()
        finally:
            self.stop_event.set()

    def shutdown(self) -> None:
        if self.stop_event.is_set():
            return
        self.stop_event.set()
        with self.lock:
            self.state.touch(status="stale")
            payload = self.state.as_dict()
        self._publish_json(self._state_topic(self.agent_id), payload, retain=True)
        self.client.disconnect()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FoxMQ warm-up agent")
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--peer-id")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--username", default="swarm")
    parser.add_argument("--password", default="swarm123")
    parser.add_argument("--role", default="carrier")
    parser.add_argument("--status", default="ready")
    parser.add_argument("--heartbeat-interval", type=float, default=2.0)
    parser.add_argument("--stale-after-ms", type=int, default=6000)
    return parser.parse_args()


def install_signal_handlers(agent: WarmupAgent) -> None:
    def handle_signal(signum, frame) -> None:
        del frame
        log(agent.agent_id, "SIGNAL", f"received {signal.Signals(signum).name}")
        agent.shutdown()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)


if __name__ == "__main__":
    agent = WarmupAgent(parse_args())
    install_signal_handlers(agent)
    agent.run()
