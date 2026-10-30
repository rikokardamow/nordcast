#!/bin/zsh
# Every minute: reload any nordcast agent launchd has lost, and log it. Twice
# agents were unloaded with their plists left in place and no log entry
# (notes/incidents.md); the timestamps here are how to find out by what.
# To unload on purpose: ops/uninstall.sh, or touch the pause file below.
set -u
launchctl=${LAUNCHCTL:-/bin/launchctl}
agents="$HOME/Library/LaunchAgents"
pause="$HOME/Library/Logs/nordcast/watchdog.pause"
[[ -e $pause ]] && exit 0
domain="gui/$(id -u)"
for label in nordcast.archive nordcast.jobs nordcast.stack; do
  plist="$agents/$label.plist"
  [[ -f $plist ]] || continue  # uninstalled, not lost
  "$launchctl" print "$domain/$label" >/dev/null 2>&1 && continue
  if "$launchctl" bootstrap "$domain" "$plist" 2>/dev/null; then
    echo "$(date -u +%FT%TZ) reloaded $label: it was unloaded"
  else
    echo "$(date -u +%FT%TZ) $label is unloaded and failed to reload"
  fi
done
