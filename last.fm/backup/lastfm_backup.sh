#!/usr/bin/bash

if [[ ! -v USERS ]]; then
    USERS=""
fi
if [[ ! -v TYPES ]]; then
    TYPES="scrobbles loved"
fi
if [[ -z $1 ]]; then
    echo "Root directory must be specified"
    exit 1
fi
ROOTDIR="$1"
DATADIR="$ROOTDIR/data"
MAXRUN="2h"
MAXDIFF=50
RC=0

trap "exit 1" SIGINT SIGTERM

for u in $USERS; do
    if [[ ! -a "$DATADIR/$u" ]]; then
        mkdir -p "$DATADIR/$u"
    fi

    TYPERC=0
    for t in $TYPES; do
        FILENAME="$DATADIR/$u/${u}_${t}_$(date -Iminutes)"
        LASTBACKUP="$(find "$DATADIR/$u" -name "*_${t}_*" | sort -r | head -n 1)"
        echo "Processing user $u (type: $t, destination: $FILENAME)"
        SECONDS=0
        timeout --foreground $MAXRUN python2.7 \
                "$ROOTDIR/lastexport.py" -u "$u" -o "$FILENAME" -t $t
        echo "Download finished in $SECONDS seconds"
        if [[ $? -ne 0 || ! -s $FILENAME ]]; then
            TYPERC=1
        else
            NEWCOUNT="$(wc -l "$FILENAME" | awk '{ print $1; }')"
            if [[ -z $LASTBACKUP ]]; then
                OLDCOUNT=0
            else
                OLDCOUNT="$(wc -l "$LASTBACKUP" | awk '{ print $1; }')"
            fi
            if (( $NEWCOUNT - $OLDCOUNT < $MAXDIFF )); then
                find "$DATADIR/$u/" -name "*_${t}_*" -mtime +7 -exec rm -f {} \;
            else
                echo "Scrobble difference between last two backups is too big"
                echo -e "Old: $OLDCOUNT\nNew: $NEWCOUNT"
                echo "Skipping old backups cleanup..."
            fi
        fi
    done

    if [[ $TYPERC -ne 0 && $RC -ne 0 ]]; then
        RC=1
    fi
done

exit $RC
