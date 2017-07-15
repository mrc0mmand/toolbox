#!/usr/bin/env python3

# Simple python script for Last.FM profile database backup
#
# Features:
#  - local SQLite database for data storage
#  - incremental backups
#  - export to plaintext
#  - statistics
#
# Basic usage (see ./lastfm-backup.py --help):
#  1) First sync
#    $ ./lastfm-backup.py -u mrc0mmand -s  # full backup of scrobbles
#    $ ./lastfm-backup.py -u mrc0mmand -l  # full backup of loved tracks
#    All future executions of the above commands will do an incremental backup
#    instead of a full one (until the corresponding DB is deleted)
#
#  2) Re-sync (useful when the first sync unexpectedly ended)
#    $ ./lastfm-backup.py -u mrc0mmand -s --force
#    This forces a full backup, but skips tracks already saved in the DB
#
#  3) Export to a plaintext file
#    $ ./lastfm-backup.py -u mrc0mmand -s --export exp.txt
#    This will export all scrobbles of given user into a tab-separated file
#    exp.txt
#    Export format:
#      timestamp artist artist_mbid track track_mbid album album_mbid
#
#    $ ./lastfm-backup.py -u mrc0mmand -s --export exp.txt --separator \;
#    Same as above, but with a semicolon as a separator instead of a tab
#
# Supported srobble types: recenttracks, lovedtracks
#
# API key:
#  An API key needs to be set up before the script can be used. Go to
#  https://www.last.fm/api/account/create, fill in required info, and
#  copy and paste the shown API key into the variable API_KEY below.
#

# MIT License
#
# Copyright (c) [2017] [Frantisek Sumsal <frantisek@sumsal.cz>]
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from datetime import datetime
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
    db = sqlite3.connect(args.dbname)

    for scrobble_type in args.stypes:
        processed = 0
        stored = 0
        page = 1
        end = False
        res = lastfm_get_scrobbles(args.username, page, scrobble_type)
        page_count = int(res[scrobble_type]["@attr"]["totalPages"])

        db_init(db, args.username, scrobble_type, args.drop)
        last_ts = db_get_last_ts(db, args.username, scrobble_type)

        print("[Backup] User: {}, type: {}".format(args.username, scrobble_type))
        while page <= page_count and not end:
            for track in lastfm_process_tracks(res, scrobble_type):
                # Check if the processed track is already in the DB.
                # If so, end the processing, as the remaining tracks
                # were already saved
                if track["ts"] <= last_ts:
                    end = True
                    print("Found track from the last backup, skipping the rest.")
                    break

                rv = db_save_track(db, track, args.username, scrobble_type)
                stored += rv
                processed += 1

            print("[Stats] pages: {}/{}, processed: {} tracks, stored: {} tracks"
                    .format(page, page_count, processed, stored))
            page += 1
            res = lastfm_get_scrobbles(args.username, page, scrobble_type)

    db.close()

# Initialize database (create a data table if it doesn't exist)
def db_init(db, username, scrobble_type, drop=False):
    cur = db.cursor()
    if drop:
        cur.execute("DROP TABLE IF EXISTS {}_{}".format(username, scrobble_type))

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
    db.close()

# Get some overall statistics about saved data
def db_stats():
    db = sqlite3.connect(args.dbname)
    db.row_factory = sqlite3.Row

    print("[{}]".format(args.username))

    if "recenttracks" in args.stypes:
        cur = db.cursor()
        # Overall statistics
        cur.execute("SELECT COUNT(*) AS total,"
                    "COUNT(DISTINCT artist) AS artists,"
                    "COUNT(DISTINCT artist_mbid) AS artists_mbid,"
                    "COUNT(DISTINCT track) AS tracks,"
                    "COUNT(DISTINCT track_mbid) AS tracks_mbid,"
                    "COUNT(DISTINCT album) AS albums,"
                    "COUNT(DISTINCT album_mbid) AS albums_mbid "
                    "FROM {}_{}".format(args.username, "recenttracks"))
        res = cur.fetchone()
        print("\tscrobbles: {}\n"
              "\tartists: {} (MBIDs: {})\n"
              "\tatracks: {} (MBIDs: {})\n"
              "\talbums: {} (MBIDs: {})"
              .format(res["total"], res["artists"], res["artists_mbid"],
                  res["tracks"], res["tracks_mbid"], res["albums"],
                  res["albums_mbid"]))
        # First scrobble
        cur.execute("SELECT * FROM {}_{} ORDER BY timestamp ASC LIMIT 1"
                .format(args.username, "recenttracks"))
        res = cur.fetchone()
        dt = datetime.fromtimestamp(res["timestamp"])
        print("\tfirst scrobble:\n"
              "\t\tdate: {}\n"
              "\t\tartist: {}\n"
              "\t\ttrack: {}\n"
              "\t\talbum: {}"
              .format(dt, res["artist"], res["track"], res["album"]))
        # Last scrobble
        cur.execute("SELECT * FROM {}_{} ORDER BY timestamp DESC LIMIT 1"
                .format(args.username, "recenttracks"))
        res = cur.fetchone()
        dt = datetime.fromtimestamp(res["timestamp"])
        print("\tlast scrobble:\n"
              "\t\tdate: {}\n"
              "\t\tartist: {}\n"
              "\t\ttrack: {}\n"
              "\t\talbum: {}"
              .format(dt, res["artist"], res["track"], res["album"]))

    if "lovedtracks" in args.stypes:
        cur = db.cursor()
        cur.execute("SELECT COUNT(*) AS total FROM {}_{}"
                .format(args.username, "lovedtracks"))
        res = cur.fetchone()
        print("\tloved tracks: {}".format(res["total"]))

    db.close()

if __name__ == "__main__":
    if not API_KEY:
        print("Missing API key")
        sys.exit(1)

    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--db", dest="dbname", default="lastfm-backup.db3",
            help="SQLite database name")
    parser.add_argument("-u", "--user", dest="username", default=None,
            help="Last.FM user name", required=True)
    parser.add_argument("--force", action="store_true",
            help="re-download all tracks (don't check for the last stored "
                 "timestamp)")
    parser.add_argument("--drop", action="store_true",
            help="Drop the selected data table before scrobble processing")

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

    stats_opts = parser.add_argument_group("Statistics")
    stats_opts.add_argument("--stats", action="store_true",
            help="Print statistics for given username/scrobble type combination")

    args = parser.parse_args()

    if not re.match("^[a-zA-Z][a-zA-Z0-9\-_]+$", args.username):
        sys.stderr.write("Invalid username (only letters, numbers, - and _,"
                " must begin with a letter)\n")
        sys.exit(1)

    if not args.stypes:
        sys.stderr.write("At least one scrobble type must be selected\n")
        sys.exit(1)

    if args.export:
        if len(args.stypes) > 1:
            sys.stderr.write("Only one scrobble type can be selected"
                             "for export\n")
            sys.exit(1)
        db_export(args.stypes[0])
    elif args.stats:
        db_stats()
    else:
        lastfm_process()
