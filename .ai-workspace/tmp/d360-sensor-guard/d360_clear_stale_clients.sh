#!/usr/bin/env bash
set -o pipefail

LOCK=/run/lock/d360-stale-client-cleanup.lock
PORTS='9090 5001'

log() { printf '[d360-stale-clients] %s\n' "$*"; }

exec 8>"$LOCK"
flock -n 8 || exit 0

[[ ${EUID:-$(id -u)} -eq 0 ]] || { log '必须以root运行'; exit 1; }

current_ips="$(ip -4 -o addr show 2>/dev/null | awk '{split($4,a,"/"); print a[1]}')"
[[ -n "$current_ips" ]] || { log '无法读取当前IPv4，fail-closed'; exit 1; }

is_current_ip() {
  local candidate="$1"
  printf '%s\n' "$current_ips" | grep -Fxq "$candidate"
}

closed=0
while read -r recv_q send_q local_endpoint peer_endpoint; do
  [[ -n "${local_endpoint:-}" ]] || continue
  local_port="${local_endpoint##*:}"
  local_ip="${local_endpoint%:*}"
  case " $PORTS " in
    *" $local_port "*) ;;
    *) continue ;;
  esac

  if is_current_ip "$local_ip"; then
    continue
  fi

  log "关闭旧连接 local=$local_endpoint peer=$peer_endpoint send_q=$send_q"
  ss -K state established "( src = $local_ip and sport = $local_port )" >/dev/null 2>&1 || true
  closed=$((closed + 1))
done < <(ss -Htn state established 2>/dev/null || true)

log "完成：关闭旧IP连接=$closed"
