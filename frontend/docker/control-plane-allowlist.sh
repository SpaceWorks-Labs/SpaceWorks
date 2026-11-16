#!/bin/sh
# Validate proxy inputs before they can become nginx directives.

cp_valid_port() (
  case "$1" in ''|*[!0-9]*|0*|??????*) return 1 ;; esac
  [ "$1" -le 65535 ]
)

cp_valid_ipv4() (
  address="$1"; count=0
  case "$address" in ''|*[!0-9.]*) return 1 ;; esac
  while :; do
    octet="${address%%.*}"
    case "$octet" in ''|0?*|????*) return 1 ;; esac
    [ "$octet" -le 255 ] || return 1
    count=$((count + 1))
    case "$address" in
      *.*) address="${address#*.}" ;;
      *) break ;;
    esac
  done
  [ "$count" -eq 4 ]
)

cp_valid_ipv6() (
  address="$1"; count=0; compressed=false
  case "$address" in ''|*[!0-9A-Fa-f:]*|*:::*) return 1 ;; esac
  case "$address" in
    *::*)
      compressed=true
      left="${address%%::*}"; right="${address#*::}"
      case "$right" in *::*) return 1 ;; esac
      ;;
    *) left="$address"; right='' ;;
  esac
  for side in "$left" "$right"; do
    [ -n "$side" ] || continue
    case "$side" in :*|*:) return 1 ;; esac
    while :; do
      group="${side%%:*}"
      case "$group" in ''|?????*) return 1 ;; esac
      count=$((count + 1))
      case "$side" in
        *:*) side="${side#*:}" ;;
        *) break ;;
      esac
    done
  done
  if [ "$compressed" = true ]; then
    [ "$count" -le 7 ]
  else
    [ "$count" -eq 8 ]
  fi
)

cp_valid_cidr() (
  address="${1%%/*}"; maximum=32
  case "$address" in
    *:*) cp_valid_ipv6 "$address" || return 1; maximum=128 ;;
    *) cp_valid_ipv4 "$address" || return 1 ;;
  esac
  case "$1" in
    */*)
      prefix="${1#*/}"
      case "$prefix" in ''|*[!0-9]*|0?*|????*) return 1 ;; esac
      [ "$prefix" -le "$maximum" ] || return 1
      ;;
  esac
)

cp_valid_cidr_list() (
  entries="$1"; count=0
  [ "${#entries}" -le 1024 ] || return 1
  case "$entries" in ''|' '*|*' '|*'  '*|*[!0-9A-Fa-f:./\ ]*) return 1 ;; esac
  while :; do
    cp_valid_cidr "${entries%% *}" || return 1
    count=$((count + 1))
    [ "$count" -le 32 ] || return 1
    case "$entries" in
      *' '*) entries="${entries#* }" ;;
      *) break ;;
    esac
  done
)
