#!/usr/bin/env bash
set -euo pipefail
# Update VSCode 
# Blame: Josh Burks <jeburks2@asu.edu> 2025-11-18
out="code-$(date +%F).tgz"
wget -O "$out" 'https://code.visualstudio.com/sha/download?build=stable&os=linux-x64'
tar -xzf "$out"
rm -f "$out"
version=$(./VSCode-linux-x64/bin/code -v | head -n1)
mv -- "VSCode-linux-x64" "$version"
[ -L latest ] && unlink latest
ln -s -- "$version" latest
if [[ -x ./latest/bin/code ]]; then
    echo "Update completed"
else
    echo "Error: ./latest/bin/code missing or not executable" >&2
    exit 1
fi

