#!/usr/bin/env bash
# run_limited <seconds> <command> [args...]
# Runs one harness stage with a time limit. Returns the command's exit code, or 124 when the limit was reached
# (the same code as coreutils `timeout`).
#
# Why not plain `timeout`: under Git Bash on Windows, `timeout` does not stop a native node.exe. In the 2026-11-23
# closeout one `ui` stage hung for 65 minutes past its 2400 s limit and was stopped by hand (report 11, G.3 and I-5).
# On Windows this function therefore stops the stage's whole native process tree (node and its headless Edge) with
# taskkill. On other systems it uses `timeout`, which works there.
run_limited() {
  local limit=$1
  shift
  if ! command -v taskkill >/dev/null 2>&1; then
    timeout --kill-after=10 "$limit" "$@"
    return
  fi
  "$@" &
  local pid=$! start=$SECONDS winpid
  while kill -0 "$pid" 2>/dev/null; do
    if (( SECONDS - start >= limit )); then
      # Read the Windows PID only now: after the exec it is node.exe's own PID.
      winpid=$(cat "/proc/$pid/winpid" 2>/dev/null)
      echo "watchdog: still running after ${limit}s; stopping its process tree (Windows PID ${winpid:-unknown})" >&2
      [ -n "$winpid" ] && taskkill //PID "$winpid" //T //F >/dev/null 2>&1
      kill -9 "$pid" 2>/dev/null
      wait "$pid" 2>/dev/null
      return 124
    fi
    sleep 1
  done
  wait "$pid"
}
