#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

fail() {
  local message=$1
  if [[ ! -t 2 && -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
    if [[ -x /usr/bin/kdialog ]]; then
      /usr/bin/kdialog --title "ERPT-BR" --error "$message" >/dev/null 2>&1 || true
    elif [[ -x /usr/bin/zenity ]]; then
      /usr/bin/zenity --title="ERPT-BR" --error --text="$message" >/dev/null 2>&1 || true
    fi
  fi
  printf 'ERPT-BR: %s\n' "$message" >&2
  exit "${2:-1}"
}

[[ "$(uname -s)" == "Linux" ]] || fail "este pacote e exclusivo para Linux x86_64."
case "$(uname -m)" in
  x86_64|amd64) ;;
  *) fail "arquitetura nao suportada; use Linux x86_64." ;;
esac
(( EUID != 0 )) || fail "nao execute o ERPT-BR com sudo/root."

launcher=${BASH_SOURCE[0]}
[[ ! -L "$launcher" ]] || fail "o launcher nao pode ser um link simbolico."
package_root=$(CDPATH= cd -- "$(dirname -- "$launcher")" && pwd -P)
internal="$package_root/interno/INICIAR_LINUX.sh"
[[ -f "$internal" && ! -L "$internal" ]] || fail "pacote incompleto: interno/INICIAR_LINUX.sh ausente."

export ERPTBR_INTERNAL_CALL=1
exec /usr/bin/env bash "$internal" "$package_root"
