#!/usr/bin/env python3

# Supported srobble types: recenttracks, lovedtracks

import argparse
import requests
import sqlite3
import time
import json
import sys
import re

API_KEY=""

# Get a page of scrobbles from Last.FM
def lastfm_get_scrobbles(username, page, scrobble_type):
    baseurl = "http://ws.audioscrobbler.com/2.0/?"
    urlvars = {
        "api_key" : API_KEY,
        "format"  : "json",
        "limit"   : 200, # Max limit is 200
        "method"  : "user.get{}".format(scrobble_type),
        "page"    : page,
        "user"    : username
    }

    for interval in (1, 5, 10, 60, 120, 180):
        try:
            f = requests.get(baseurl,data=urlvars, timeout=5)
            if f.status_code != requests.codes.ok:
                raise Exception("Timeout reached ({})".format(f.status_code))
            else:
                break
        except Exception as e:
            last_exc = e
            print("Exception occured, retrying in {}s: {}".format(interval, e))
            time.sleep(interval)
    else:
        print("Failed to open page {}".format(page))
        raise last_exc

    response = json.loads(f.text)
    f.close()

    #print(json.dumps(response, indent=4))
    return response

def lastfm_process_tracks(track_page, track_type):
    for track in track_page[track_type]["track"]:
        try:
            if track["@attr"]["nowplaying"]:
                continue
        except:
            pass

        # Loved tracks have the text info nested in a "name" tag
        name_tag = "#text" if track_type == "recenttracks" else "name"

        data = {
            "artist"      : track["artist"][name_tag],
            "artist_mbid" : track["artist"]["mbid"],
            "name"        : track["name"],
            "name_mbid"   : track["mbid"],
            "ts"          : int(track["date"]["uts"])
        }

        # Loved tracks usually don't contain album
        if "album" in track:
            data["album"] = track["album"][name_tag]
            data["album_mbid"] = track["album"]["mbid"]
        else:
            data["album"] = ""
            data["album_mbid"] = ""

        yield data

def lastfm_process():
    processed = 0
    stored = 0
    db = sqlite3.connect(args.dbname)

    for scrobble_type in args.stypes:
        page = 1
        res = lastfm_get_scrobbles(args.username, page, scrobble_type)
        page_count = int(res[scrobble_type]["@attr"]["totalPages"])

        db_init(db, args.username, scrobble_type)
        last_ts = db_get_last_ts(db, args.username, scrobble_type)

        while page <= page_count:
            for track in lastfm_process_tracks(res, scrobble_type):
                # Check if the processed track is already in the DB.
                # If so, end the processing, as the remaining tracks
                # were already saved
                if track["ts"] <= last_ts:
                    # Set page_count to 0 to break out of the outer loop
                    page_count = 0
                    print("Found track from the last backup, skipping the rest.")
                    break

                rv = db_save_track(db, track, args.username, scrobble_type)
                stored += rv
                processed += 1

            print("[Stats] pages: {}/{}, processed: {} tracks, stored: {} tracks"
                    .format(page, page_count, processed, stored))
            page += 1
            res = lastfm_get_scrobbles(args.username, page, scrobble_type)

# Initialize database (create a data table if it doesn't exist)
def db_init(db, username, scrobble_type):
    cur = db.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS {}_{}("
            "timestamp INTEGER PRIMARY KEY,"
            "artist DATA NOT NULL,"
            "artist_mbid DATA,"
            "track DATA NOT NULL,"
            "track_mbid DATA,"
            "album DATA,"
            "album_mbid DATA)".format(username, scrobble_type))
    db.commit()

# Get the last timestamp from given db/table combination
# This timestamp is used to find the end of the previous backup, to create
# an incremental backup instead of another full one. This behavior can
# be overridden using --force option.
def db_get_last_ts(db, username, scrobble_type):
    # We want to re-download all tracks
    if args.force:
        return 0

    cur = db.cursor()
    cur.execute("SELECT timestamp FROM {}_{} ORDER BY timestamp DESC LIMIT 1"
            .format(username, scrobble_type))
    res = cur.fetchone()
    if res:
        return res[0]
    else:
        return 0

# Save the given track into the DB
def db_save_track(db, track, username, scrobble_type):
    cur = db.cursor()
    cur.execute("INSERT OR IGNORE INTO {}_{} VALUES(?, ?, ?, ?, ?, ?, ?)"
            .format(username, scrobble_type),
            (track["ts"], track["artist"], track["artist_mbid"], track["name"],
                track["name_mbid"], track["album"], track["album_mbid"]))
    db.commit()

    return cur.rowcount

# Export tracks of given scrobble_type from the database
def db_export(scrobble_type):
    db = sqlite3.connect(args.dbname)
    out = open(args.export, "w")
    cur = db.cursor()
    cur.execute("SELECT * FROM {}_{} ORDER BY timestamp DESC"
            .format(args.username, scrobble_type))
    for row in cur:
        out.write(args.separator.join(str(x) for x in row) + "\n")
    out.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # TODO: Stats options
    # --stats (print all stats)
    # ...
    parser.add_argument("-d", "--db", dest="dbname", default="lastfm-backup.db3",
            help="SQLite database name")
    parser.add_argument("-u", "--user", dest="username", default=None,
            help="Last.FM user name", required=True)
    parser.add_argument("--force", action="store_true",
            help="re-download all tracks (don't check for the last stored "
                 "timestamp)")

    scrobble_types = parser.add_argument_group("Scrobble type")
    scrobble_types.add_argument("-s", "--scrobbles", dest="stypes",
            default=None, help="scrobbles", action="append_const",
            const="recenttracks")
    scrobble_types.add_argument("-l", "--loved", dest="stypes",
            default=None, help="loved tracks", action="append_const",
            const="lovedtracks")

    export_opts = parser.add_argument_group("Export")
    export_opts.add_argument("-e", "--export", dest="export", default=None,
            metavar="FILENAME",
            help="Export selected database into a tab-separated text file")
    export_opts.add_argument("--separator", default="\t",
            help="Override default column separator (TAB)")

    args = parser.parse_args()

    if not args.stypes:
        sys.stderr.write("At least one scrobble type must be selected\n")
        sys.exit(1)

    if args.export:
        if len(args.stypes) > 1:
            sys.stderr.write("Only one scrobble type can be selected"
                             "for export\n")
            sys.exit(1)
        db_export(args.stypes[0])
    else:
        lastfm_process()
