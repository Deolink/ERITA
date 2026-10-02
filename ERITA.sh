#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

fail() {
  local message=$1
  if [[ ! -t 2 && -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
    if [[ -x /usr/bin/kdialog ]]; then
      /usr/bin/kdialog --title "ERITA" --error "$message" >/dev/null 2>&1 || true
    elif [[ -x /usr/bin/zenity ]]; then
      /usr/bin/zenity --title="ERITA" --error --text="$message" >/dev/null 2>&1 || true
    fi
  fi
  printf 'ERITA: %s\n' "$message" >&2
  exit "${2:-1}"
}

[[ "$(uname -s)" == "Linux" ]] || fail "questo pacchetto funziona solo su Linux x86_64."
case "$(uname -m)" in
  x86_64|amd64) ;;
  *) fail "architettura non supportata; usa Linux x86_64." ;;
esac
(( EUID != 0 )) || fail "non eseguire ERITA con sudo/root."

launcher=${BASH_SOURCE[0]}
[[ ! -L "$launcher" ]] || fail "il launcher non può essere un link simbolico."
package_root=$(CDPATH= cd -- "$(dirname -- "$launcher")" && pwd -P)
internal="$package_root/interno/INICIAR_LINUX.sh"
[[ -f "$internal" && ! -L "$internal" ]] || fail "pacchetto incompleto: manca interno/INICIAR_LINUX.sh."

export ERPTBR_INTERNAL_CALL=1
exec /usr/bin/env bash "$internal" "$package_root"
