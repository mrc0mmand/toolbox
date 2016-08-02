#!/bin/bash

USERMODE=0

if [[ $1 == "-u" ]]; then
    USERMODE=1
    DATADIR="$2"
else
    DATADIR="$1"
fi

if [[ -z $DATADIR ]]; then
    echo "Data dir must be specified"
    exit 1
fi

FORMAT="<pre>
[%s]
\tscrobbles: %d
\tloved: %d
\tinvalid: %d
\tscrobble info:
\t\tfirst scrobble:
\t\t\tdate: %s
\t\t\tartist: %s
\t\t\ttrack: %s
\t\t\talbum: %s
\t\tlast scrobble:
\t\t\tdate: %s
\t\t\tartist: %s
\t\t\ttrack: %s
\t\t\talbum: %s
\t\tunique MBIDs:
\t\t\ttrack: %d
\t\t\tartist: %d
\t\t\talbum: %d
\tlast backups:
\t\tscrobbles: %s
\t\tloved: %s\n
</pre>"

function get_user_stats() {
    dir="$1"
    user="$(basename "$dir")"
    f_scrobbles="$(find "$dir" -type f -name "*_scrobbles_*" |
                   sort -r | head -n1)"
    f_loved="$(find "$dir" -type f -name "*_loved_*" |
               sort -r | head -n1)"
    if [[ ! -f $f_scrobbles || ! -f $f_loved ]]; then
        echo "Incomplete data for user $user"
        return
    fi
    s_first="$(find "$dir" -type f -name "*_scrobbles_*" |
               sort -r | head -n1 | xargs grep -v "^0.*" | tail -n 1 |
               sed 's/\t\t/\t \t/g')"
    s_last="$(find "$dir" -type f -name "*_scrobbles_*" |
               sort -r | head -n1 | xargs head -n 1 | sed 's/\t\t/\t \t/g')"
    IFS=$'\t' read -r -a a_first <<< "$s_first"
    IFS=$'\t' read -r -a a_last <<< "$s_last"
    d_first="$(date --date="@${a_first[0]}")"
    d_last="$(date --date="@${a_last[0]}")"
    d_scrobbles="$(echo "$f_scrobbles" | rev | cut -d'_' -f1 |
                   rev | xargs date --date)"
    d_loved="$(echo "$f_loved" | rev | cut -d'_' -f1 |
                   rev | xargs date --date)"
    scrobbles="$(wc -l "$f_scrobbles" | awk '{print $1;}')"
    loved="$(wc -l "$f_loved" | awk '{print $1;}')"
    invalid_scrobbles="$(grep -P "^0\t.*" "$f_scrobbles" | wc -l)"
    mbid_track="$(awk -F '\t' '{print $5;}' "$f_scrobbles" |
                  sort | uniq | wc -l)"
    mbid_artist="$(awk -F '\t' '{print $6;}' "$f_scrobbles" |
                  sort | uniq | wc -l)"
    mbid_album="$(awk -F '\t' '{print $7;}' "$f_scrobbles" |
                  sort | uniq | wc -l)"

    printf "$FORMAT" "$user" $scrobbles $loved $invalid_scrobbles\
           "$d_first" "${a_first[2]}" "${a_first[1]}" "${a_first[3]}" \
           "$d_last" "${a_last[2]}" "${a_last[1]}" "${a_last[3]}" \
           $mbid_track $mbid_artist $mbid_album \
           "$d_scrobbles" "$d_loved"
}

if [[ $USERMODE -eq 1 ]]; then
    get_user_stats "$DATADIR"
else
    while read -r dir
    do
        get_user_stats "$dir"
    done < <(find "$DATADIR" -mindepth 1 -maxdepth 1 -type d ! -name "_oneshot" | sort)
fi
