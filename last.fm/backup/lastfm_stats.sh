#!/bin/bash

if [[ -z $1 ]]; then
    echo "Data dir must be specified"
    exit 1
fi

DATA_DIR="$1"
FORMAT="[%s]
\tscrobbles: %d
\tloved: %d
\tscrobbles:
\t\tfirst scrobble: %s
\t\tlast scrobble: %s
\tlast backups:
\t\tS: %s
\t\tL: %s\n"

while read -r dir
do
    user="$(basename $dir)"
    f_scrobbles="$(find "$dir" -type f -name "*_scrobbles_*" |
                   sort -r | head -n1)"
    f_loved="$(find "$dir" -type f -name "*_loved_*" |
               sort -r | head -n1)"
    d_first="$(date --date="@$(find "$dir" -type f -name "*_scrobbles_*" |
               sort -r | head -n1 | xargs tail -n 1 |
               awk '{print $1; }')")"
    d_last="$(date --date="@$(find "$dir" -type f -name "*_scrobbles_*" |
               sort -r | head -n1 | xargs head -n 1 |
               awk '{print $1; }')")"
    d_scrobbles="$(echo "$f_scrobbles" | rev | cut -d'_' -f1 | 
                   rev | xargs date --date)"
    d_loved="$(echo "$f_loved" | rev | cut -d'_' -f1 | 
                   rev | xargs date --date)"
    scrobbles="$(wc -l "$f_scrobbles" | awk '{print $1;}')"
    loved="$(wc -l "$f_loved" | awk '{print $1;}')"

    printf "$FORMAT" "$user" $scrobbles $loved "$d_first" "$d_last" "$d_scrobbles" "$d_loved"

done < <(find "$DATA_DIR" -mindepth 1 -maxdepth 1 -type d ! -name "_oneshot")
