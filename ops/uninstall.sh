#!/bin/zsh
# Stop and remove the launchd agents. Data and code are left alone.
# the watchdog first, so it can't reload what this removes
launchctl bootout "gui/$(id -u)/nordcast.watchdog" 2>/dev/null
for src in "$(dirname "$0")"/launchd/*.plist; do
  label=$(basename "$src" .plist)
  launchctl bootout "gui/$(id -u)/$label" 2>/dev/null && echo "stopped $label"
  rm -f "$HOME/Library/LaunchAgents/$label.plist"
done
