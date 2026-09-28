#!/bin/sh
# Install the Tower CLI launcher into a bin directory (default: ~/.local/bin).
#
# The launcher runs the tower package from this repository checkout, so the
# installed CLI always reflects the working tree. Re-run this script after
# moving the repository to refresh the launcher path.
#
# Usage: install.sh [bin-dir]

set -eu

repo_root="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
bin_dir="${1:-$HOME/.local/bin}"
launcher="$bin_dir/tower"

if [ -e "$launcher" ] && ! grep -q "^# Tower CLI launcher" "$launcher" 2>/dev/null; then
    printf 'error: %s exists and is not a tower launcher; refusing to overwrite\n' "$launcher" >&2
    exit 1
fi

mkdir -p "$bin_dir"
cat > "$launcher" <<EOF
#!/bin/sh
# Tower CLI launcher (installed by install.sh from $repo_root)
PYTHONPATH="$repo_root\${PYTHONPATH:+:\$PYTHONPATH}"
export PYTHONPATH
exec python3 -m tower "\$@"
EOF
chmod +x "$launcher"

case ":$PATH:" in
    *":$bin_dir:"*) ;;
    *)
        printf 'warning: %s is not on PATH; add it to your shell profile\n' "$bin_dir" >&2
        ;;
esac

printf 'Installed tower to %s (running %s)\n' "$launcher" "$repo_root"
