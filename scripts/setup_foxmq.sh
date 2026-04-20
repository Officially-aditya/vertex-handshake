#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FOXMQ_BIN="${ROOT_DIR}/foxmq"
FOXMQ_DIR="${ROOT_DIR}/foxmq.d"
FOXMQ_USERNAME="${FOXMQ_USERNAME:-swarm}"
FOXMQ_PASSWORD="${FOXMQ_PASSWORD:-swarm123}"

if [[ -x "${FOXMQ_BIN}" ]]; then
  echo "foxmq binary already present at ${FOXMQ_BIN}"
else
  case "$(uname -s)" in
    Darwin)
      ARCHIVE_URL="https://github.com/tashigit/foxmq/releases/download/v0.3.1/foxmq_0.3.1_macos-universal.zip"
      ;;
    Linux)
      ARCHIVE_URL="https://github.com/tashigit/foxmq/releases/download/v0.3.1/foxmq_0.3.1_linux-amd64.zip"
      ;;
    *)
      echo "Unsupported OS for automated FoxMQ setup" >&2
      exit 1
      ;;
  esac

  TMP_DIR="$(mktemp -d)"
  ARCHIVE_PATH="${TMP_DIR}/foxmq.zip"

  curl -L "${ARCHIVE_URL}" -o "${ARCHIVE_PATH}"
  unzip -o "${ARCHIVE_PATH}" -d "${ROOT_DIR}"
  chmod +x "${FOXMQ_BIN}"
  rm -rf "${TMP_DIR}"
fi

mkdir -p "${FOXMQ_DIR}"

if [[ ! -f "${FOXMQ_DIR}/address-book.toml" ]]; then
  "${FOXMQ_BIN}" address-book from-range 127.0.0.1 19793 19793
fi

if [[ ! -f "${FOXMQ_DIR}/users.toml" ]]; then
  "${FOXMQ_BIN}" user add "${FOXMQ_USERNAME}" "${FOXMQ_PASSWORD}"
fi

echo "FoxMQ setup complete."
echo "Start the broker with:"
echo "  ./foxmq run --secret-key-file=foxmq.d/key_0.pem"
