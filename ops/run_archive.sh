#!/bin/zsh
# Every minute: append Energinet's real-time feeds to ~/nordcast-archive,
# push it hourly. Idempotent, so a missed or doubled run costs nothing.
set -u
export PATH=/opt/homebrew/bin:/usr/bin:/bin
cd "$(dirname "$0")/.."
uv run --quiet --script jobs/archive.py
