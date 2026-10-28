#!/bin/zsh
# Start Docker (Colima), the local database and keep them up. Run at login.
set -u
export PATH=/opt/homebrew/bin:/usr/bin:/bin
cd "$(dirname "$0")/.."
colima status >/dev/null 2>&1 || colima start
until docker info >/dev/null 2>&1; do sleep 5; done
supabase status >/dev/null 2>&1 || supabase start
echo "$(date -u +%FT%TZ) stack up"
