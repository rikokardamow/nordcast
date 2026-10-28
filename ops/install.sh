#!/bin/zsh
# Install the launchd agents in ops/launchd. Logs: ~/Library/Logs/nordcast/
set -eu
repo=$(cd "$(dirname "$0")/.." && pwd)
logs="$HOME/Library/Logs/nordcast"
agents="$HOME/Library/LaunchAgents"
mkdir -p "$logs" "$agents"
for src in "$repo"/ops/launchd/*.plist; do
  label=$(basename "$src" .plist)
  dest="$agents/$label.plist"
  sed -e "s#REPO#$repo#g" -e "s#LOGS#$logs#g" "$src" > "$dest"
  launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$dest"
  echo "loaded $label"
done
