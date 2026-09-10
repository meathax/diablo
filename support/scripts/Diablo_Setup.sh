#!/bin/sh
# Enable the resident Diablo MiSTer-Main handler for both visible RBF entries.
set -eu

root=${DIABLO_SD_ROOT:-/media/fat}
ini="$root/MiSTer.ini"
[ -f "$ini" ] || ini="$root/mister.ini"
[ -L "$ini" ] && { echo "Refusing symlinked MiSTer.ini" >&2; exit 1; }

lock="$root/.diablo-setup.lock"
mkdir "$lock" || { echo "Diablo setup already running" >&2; exit 1; }
tmp="$lock/MiSTer.ini"
trap 'rm -f "$tmp"; rmdir "$lock"' EXIT HUP INT TERM

awk '
function finish() { if (in_diablo && !had_main) print "main=Diablo" ending }
{
    ending = ($0 ~ /\r$/) ? "\r" : ""
    line = $0; sub(/\r$/, "", line)
    if (line ~ /^[ \t]*\[[^]]+\][ \t]*([;#].*)?$/) {
        finish()
        section = line; sub(/^[ \t]*\[/, "", section); sub(/\].*$/, "", section)
        in_diablo = (tolower(section) == "diablo")
        if (in_diablo) found = 1
        had_main = 0
    }
    if (in_diablo && tolower(line) ~ /^[ \t]*main[ \t]*=/) {
        if (!had_main) print "main=Diablo" ending
        had_main = 1
    } else print $0
}
END {
    finish()
    if (!found) { print ""; print "[Diablo]"; print "main=Diablo" }
}' "$ini" > "$tmp"

if ! cmp -s "$ini" "$tmp"; then
    [ ! -f "$ini.diablo-backup" ] && cp -p "$ini" "$ini.diablo-backup"
    mv "$tmp" "$ini"
fi

for file in "$root/Diablo" "$root/_Other/Diablo/diablo_launcher.py" \
            "$root/_Other/Diablo/devilutionx"; do
    [ ! -f "$file" ] || chmod +x "$file"
done

echo "Diablo RBF handoff installed: [Diablo] main=Diablo"
