#!/bin/zsh
# Every minute: load what the archive pulled, freeze what's due, score
# what's out. Each job does nothing when nothing is due, so running often is
# safe. After 00:10 Copenhagen: the day's stamped file, pushed. Hourly: the
# heartbeat, pushed (only when nothing unapproved is on main), and the backup to the private nordcast-backups repo.
set -u
export PATH=/opt/homebrew/bin:/usr/bin:/bin
cd "$(dirname "$0")/.."
unset VIRTUAL_ENV DATABASE_URL BACKUP_REPO  # the shell's are energy-forecasting's
[[ -f .env ]] && { set -a; . ./.env; set +a; }
stamp() { date -u +%FT%TZ; }

# Push only the jobs' own commits. Anything else ahead of origin/main is work
# waiting for my approval, so the push is held and logged, not made.
push_own() {
  git fetch -q origin main 2>&1 || { echo "$(stamp) $1 push failed: fetch"; return; }
  local others
  others=$(git log --format='%h %s' origin/main..main | grep -vE '^[0-9a-f]+ (Heartbeat [0-9]{4}-[0-9]{2}-[0-9]{2} [0-9:]{5} UTC|Stamp dk1-[0-9-]+(, dk1-[0-9-]+)*|Scorecard [0-9]{4}-[0-9]{2}-[0-9]{2})$')
  if [[ -n $others ]]; then
    echo "$(stamp) $1 push held: unapproved commits on main: ${others//$'\n'/; }"
  else
    git push -q origin main 2>&1 || echo "$(stamp) $1 push failed"
  fi
}

uv run --quiet python jobs/pull_live.py || echo "$(stamp) pull_live failed"
uv run --quiet --group models python jobs/freeze.py || echo "$(stamp) freeze failed"
uv run --quiet python jobs/score.py || echo "$(stamp) score failed"

if [[ $(TZ=Europe/Copenhagen date +%H%M) -ge 0010 ]]; then
  if uv run --quiet python jobs/stamp_daily.py | grep -q '^Stamp'; then
    uv run --quiet python jobs/scorecard.py || echo "$(stamp) scorecard failed"
    push_own stamp
  fi
fi

# About hourly: status/heartbeat.json for the deadman on GitHub.
if uv run --quiet python jobs/heartbeat.py | grep -q '^Heartbeat'; then
  push_own heartbeat
fi

# Minute 05 of each hour; launchd's start drift can skip one, the next hour covers it.
if [[ $(date -u +%M) == 05 ]]; then
  uv run --quiet python -c 'from nordcast import backup; backup.run("hourly")'
fi
