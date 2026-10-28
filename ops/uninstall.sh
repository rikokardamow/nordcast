#!/bin/zsh
# Stop and remove the launchd agents. Data and code are left alone.
for src in "$(dirname "$0")"/launchd/*.plist; do
  label=$(basename "$src" .plist)
  launchctl bootout "gui/$(id -u)/$label" 2>/dev/null && echo "stopped $label"
  rm -f "$HOME/Library/LaunchAgents/$label.plist"
done
