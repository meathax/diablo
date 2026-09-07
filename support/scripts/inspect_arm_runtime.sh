#!/bin/sh
# Run on the identified MiSTer. Read-only; save stdout on the development host.
# Does not load a core, map physical memory, or change target libraries.
set -u
printf '%s\n' 'Diablo ARM runtime inventory v1'
uname -a
for item in /proc/cpuinfo /proc/meminfo /proc/iomem /proc/mounts; do
    printf '\n--- %s ---\n' "$item"
    if [ -r "$item" ]; then cat "$item"; else printf '%s\n' 'unavailable'; fi
done
printf '\n--- libc and page size ---\n'
if command -v getconf >/dev/null 2>&1; then
    getconf GNU_LIBC_VERSION 2>&1
    getconf PAGESIZE 2>&1
else
    printf '%s\n' 'getconf unavailable'
fi
printf '\n--- runtime files ---\n'
for directory in /lib /usr/lib /lib/arm-linux-gnueabihf /usr/lib/arm-linux-gnueabihf; do
    for library in "$directory"/ld-linux*.so* "$directory"/libc.so* \
        "$directory"/libstdc++.so* "$directory"/libgcc_s.so* \
        "$directory"/libpthread.so*; do
        [ -f "$library" ] || continue
        ls -l "$library"
        if command -v sha256sum >/dev/null 2>&1; then sha256sum "$library"; fi
        if command -v readelf >/dev/null 2>&1; then readelf -h -V "$library"; fi
    done
done
printf '\n--- storage capacity ---\n'
df -Pk
printf '\n%s\n' 'Inventory complete; missing tools/files require follow-up. No runtime acceptance implied.'
