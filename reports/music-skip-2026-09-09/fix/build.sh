#!/bin/bash
cmake --build /home/meath/.cache/diablo-arm-engine-transport --target devilutionx -j 4
result=$?
echo "$result" > /mnt/d/Arcade/AI/aCORES/Diablo/reports/music-skip-2026-09-09/fix/build.exit
exit "$result"
