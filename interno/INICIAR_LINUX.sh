#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

readonly APP_VERSION="0.9.7"
readonly RUNTIME_NAME="cpython-3.13.15+20260924-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz"
readonly RUNTIME_SIZE="34993852"
readonly RUNTIME_SHA256="d0b640eed27fbdd6f5f2bd33444aee53df2c8863f8b2a96f4094717411e3de9c"

fail() {
  local message=$1
  local code=${2:-1}
  if [[ ! -t 2 && -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
    if [[ -x /usr/bin/kdialog ]]; then
      /usr/bin/kdialog --title "ERPT-BR" --error "$message" >/dev/null 2>&1 || true
    elif [[ -x /usr/bin/zenity ]]; then
      /usr/bin/zenity --title="ERPT-BR" --error --text="$message" >/dev/null 2>&1 || true
    fi
  fi
  printf 'ERPT-BR: %s\n' "$message" >&2
  exit "$code"
}

[[ "${ERPTBR_INTERNAL_CALL:-}" == "1" ]] || fail "use ERPT-BR.sh na pasta principal." 2
[[ $# -eq 1 ]] || fail "raiz do pacote nao informada." 2
package_root=$1
[[ "$package_root" == /* ]] || fail "a raiz do pacote precisa ser absoluta."
[[ -d "$package_root" && ! -L "$package_root" ]] || fail "raiz do pacote insegura."
[[ -n "${HOME:-}" && "$HOME" == /* ]] || fail "HOME absoluto nao esta disponivel."

for command_name in sha256sum stat tar flock mktemp mv mkdir find date rmdir; do
  command -v "$command_name" >/dev/null 2>&1 || fail "comando obrigatorio ausente: $command_name"
done

sha256_file() {
  local output digest
  output=$(sha256sum -- "$1") || return 1
  digest=${output%% *}
  [[ "$digest" =~ ^[0-9a-fA-F]{64}$ ]] || return 1
  printf '%s' "${digest,,}"
}

require_regular() {
  [[ -f "$1" && ! -L "$1" ]] || fail "arquivo obrigatorio ausente ou inseguro: ${1#"$package_root/"}"
}

runtime_archive="$package_root/runtime/$RUNTIME_NAME"
requirements="$package_root/patcher/requirements-linux-x86_64.lock"
require_regular "$runtime_archive"
require_regular "$requirements"
for required in \
  "$package_root/patcher/__init__.py" \
  "$package_root/patcher/bnk.py" \
  "$package_root/patcher/engine.py" \
  "$package_root/patcher/diagnostics.py" \
  "$package_root/patcher/patch_data.py" \
  "$package_root/patcher/patcher_gui.py"; do
  require_regular "$required"
done
[[ -d "$package_root/patch_data" && ! -L "$package_root/patch_data" ]] || fail "pasta patch_data ausente ou insegura."

actual_runtime_size=$(stat -c '%s' -- "$runtime_archive") || fail "nao foi possivel medir o runtime."
[[ "$actual_runtime_size" == "$RUNTIME_SIZE" ]] || fail "runtime portatil com tamanho incorreto."
actual_runtime_hash=$(sha256_file "$runtime_archive") || fail "nao foi possivel autenticar o runtime."
[[ "$actual_runtime_hash" == "$RUNTIME_SHA256" ]] || fail "runtime portatil adulterado."

declare -A wheel_hashes=(
  ["customtkinter-5.2.2-py3-none-any.whl"]="14ad3e7cd3cb3b9eb642b9d4e8711ae80d3f79fb82545ad11258eeffb2e6b37c"
  ["darkdetect-0.8.0-py3-none-any.whl"]="a7509ccf517eaad92b31c214f593dbcf138ea8a43b2935406bbd565e15527a85"
  ["packaging-26.3-py3-none-any.whl"]="d7193f7c8e4e93f444fde0262bf90af30e16fa0ad0ad44cb553c87339b23cd1c"
  ["pycryptodome-3.23.0-cp37-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"]="c8987bd3307a39bc03df5c8e0e3d8be0c4c3518b7f044b0f4c15d1aa78f52575"
)
for wheel in "${!wheel_hashes[@]}"; do
  wheel_path="$package_root/wheelhouse/$wheel"
  require_regular "$wheel_path"
  actual=$(sha256_file "$wheel_path") || fail "nao foi possivel autenticar $wheel."
  [[ "$actual" == "${wheel_hashes[$wheel]}" ]] || fail "wheel adulterado: $wheel"
done

data_base=${XDG_DATA_HOME:-"$HOME/.local/share"}
[[ "$data_base" == /* ]] || fail "XDG_DATA_HOME precisa ser absoluto."
mkdir -p -m 700 -- "$data_base"
app_data="$data_base/ERPT-BR"
mkdir -p -m 700 -- "$app_data"
[[ -d "$app_data" && ! -L "$app_data" ]] || fail "pasta de dados do ERPT-BR insegura."

exec 9>"$app_data/.launcher.lock"
flock -n 9 || fail "outra inicializacao do ERPT-BR esta em andamento." 75

if [[ ! -t 2 ]]; then
  exec >>"$app_data/launcher.log" 2>&1
fi

runtime_root="$app_data/runtime-cpython-3.13.15-20260924"
runtime_python="$runtime_root/bin/python3.13"
runtime_marker="$runtime_root/.erpt-runtime-sha256"

validate_runtime() {
  [[ -d "$runtime_root" && ! -L "$runtime_root" ]] || return 1
  [[ -f "$runtime_python" && -x "$runtime_python" && ! -L "$runtime_python" ]] || return 1
  [[ -f "$runtime_marker" && ! -L "$runtime_marker" ]] || return 1
  [[ "$(<"$runtime_marker")" == "$RUNTIME_SHA256" ]] || return 1
  "$runtime_python" -I -S -c \
    "import struct,sys,sysconfig,tkinter; raise SystemExit(0 if sys.implementation.name == 'cpython' and sys.version_info[:3] == (3,13,15) and sys.version_info.releaselevel == 'final' and struct.calcsize('P') == 8 and sysconfig.get_platform() == 'linux-x86_64' and not sysconfig.get_config_var('Py_GIL_DISABLED') else 1)" \
    >/dev/null 2>&1
}

if ! validate_runtime; then
  staging=$(mktemp -d "$app_data/.runtime-staging.XXXXXXXX") || fail "nao foi possivel criar o staging do runtime."
  tar --extract --gzip --file "$runtime_archive" --directory "$staging" \
    --no-same-owner --no-same-permissions || fail "falha ao extrair o runtime autenticado; staging preservado em $staging"
  extracted="$staging/python"
  extracted_python="$extracted/bin/python3.13"
  [[ -d "$extracted" && ! -L "$extracted" ]] || fail "layout inesperado no runtime; staging preservado em $staging"
  [[ -f "$extracted_python" && -x "$extracted_python" && ! -L "$extracted_python" ]] || fail "Python portatil ausente; staging preservado em $staging"
  "$extracted_python" -I -S -c \
    "import struct,sys,sysconfig,tkinter; raise SystemExit(0 if sys.version_info[:3] == (3,13,15) and struct.calcsize('P') == 8 and sysconfig.get_platform() == 'linux-x86_64' and not sysconfig.get_config_var('Py_GIL_DISABLED') else 1)" \
    >/dev/null 2>&1 || fail "runtime extraido incompativel; staging preservado em $staging"
  printf '%s\n' "$RUNTIME_SHA256" > "$extracted/.erpt-runtime-sha256"
  if [[ -e "$runtime_root" || -L "$runtime_root" ]]; then
    quarantine="$app_data/runtime-invalido-$(date -u +%Y%m%dT%H%M%SZ)-$$"
    mv -- "$runtime_root" "$quarantine" || fail "runtime antigo inseguro; ele foi preservado."
  fi
  mv -- "$extracted" "$runtime_root" || fail "nao foi possivel publicar o runtime; staging preservado em $staging"
  rmdir -- "$staging" 2>/dev/null || true
  validate_runtime || fail "runtime continuou invalido depois da preparacao."
fi

lock_hash=$(sha256_file "$requirements") || fail "nao foi possivel autenticar o lock Linux."
deps_identity="$APP_VERSION:$RUNTIME_SHA256:$lock_hash"
deps_root="$app_data/deps-$APP_VERSION-linux-x86_64"
deps_marker="$deps_root/.erpt-deps-identity"

validate_deps() {
  [[ -d "$deps_root" && ! -L "$deps_root" ]] || return 1
  [[ -f "$deps_marker" && ! -L "$deps_marker" ]] || return 1
  [[ "$(<"$deps_marker")" == "$deps_identity" ]] || return 1
  [[ -z "$(find "$deps_root" -type l -print -quit)" ]] || return 1
  "$runtime_python" -I -S -c \
    "import importlib.metadata as m,sys; sys.path.insert(0,sys.argv[1]); import customtkinter; from Crypto.Cipher import AES; expected={'customtkinter':'5.2.2','darkdetect':'0.8.0','packaging':'26.3','pycryptodome':'3.23.0'}; actual={d.metadata['Name'].lower():d.version for d in m.distributions(path=[sys.argv[1]])}; raise SystemExit(0 if actual == expected else 1)" \
    "$deps_root" >/dev/null 2>&1
}

if ! validate_deps; then
  deps_staging=$(mktemp -d "$app_data/.deps-staging.XXXXXXXX") || fail "nao foi possivel criar o staging das dependencias."
  "$runtime_python" -I -m pip --isolated install \
    --disable-pip-version-check --no-input --no-index \
    --find-links "$package_root/wheelhouse" --require-hashes \
    --only-binary=:all: --no-compile --target "$deps_staging" \
    -r "$requirements" || fail "falha ao instalar as dependencias offline; staging preservado em $deps_staging"
  if [[ -n "$(find "$deps_staging" -type l -print -quit)" ]]; then
    fail "uma dependencia criou link simbolico; staging preservado em $deps_staging"
  fi
  printf '%s\n' "$deps_identity" > "$deps_staging/.erpt-deps-identity"
  if [[ -e "$deps_root" || -L "$deps_root" ]]; then
    quarantine="$app_data/deps-invalidas-$(date -u +%Y%m%dT%H%M%SZ)-$$"
    mv -- "$deps_root" "$quarantine" || fail "dependencias antigas inseguras; elas foram preservadas."
  fi
  mv -- "$deps_staging" "$deps_root" || fail "nao foi possivel publicar as dependencias offline."
  validate_deps || fail "dependencias continuaram invalidas depois da preparacao."
fi

export ERPTBR_PACKAGE_KIND="linux-portable-tar"
if [[ "${ERPTBR_INSTALL_ONLY:-}" == "1" ]]; then
  printf 'ERPT-BR %s: ambiente Linux portatil validado.\n' "$APP_VERSION"
  exit 0
fi

exec "$runtime_python" -I -S -c \
  "import runpy,sys; sys.path.extend((sys.argv[1],sys.argv[2])); runpy.run_module('patcher.patcher_gui',run_name='__main__')" \
  "$package_root" "$deps_root"
