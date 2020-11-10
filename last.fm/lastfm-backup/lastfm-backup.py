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
BASEURL = "http://ws.audioscrobbler.com/2.0/?"

class Scrobble(object):
    def __init__(self, ts=0, artist="", artist_mbid="", track="", track_mbid="",
            album="", album_mbid="", type="recenttracks"):
        self.ts = ts
        self.artist = artist
        self.artist_mbid = artist_mbid
        self.track = track
        self.track_mbid = track_mbid
        self.album = album
        self.album_mbid = album_mbid
        self.type = type

    def __str__(self):
        return "Timestamp:\t{}\nArtist:\t\t{}\nArist MBID:\t{}\nTrack:\t\t{}\n" \
               "Track MBID:\t{}\nAlbum:\t\t{}\nAlbum MBID:\t{}" \
               .format(self.ts, self.artist, self.artist_mbid, self.track,
                       self.track_mbid, self.album, self.album_mbid)

def printv(string):
    if args.verbose:
        print(string)

def url_get(url, urlvars, timeout=5):
    for interval in (1, 5, 10, 60, 120, 180):
        try:
            f = requests.get(url, params=urlvars, timeout=timeout)
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

    data = f.text
    f.close()

    return data

# Autocorrect type: artist, track, album
def lastfm_autocorrect_get(urlvars, a_type):
    data = url_get(BASEURL, urlvars)
    res = json.loads(data)

    try:
        name = res[a_type]["name"]
        if "mbid" in res[a_type]:
            mbid = res[a_type]["mbid"]
        else:
            mbid = ""
    except Exception as e:
        error = lastfm_error(res)
        if not error:
            error = e
        raise Exception("[Autocorrect]: {} autocorrection failed, reason: {}"
                "(name: {}, mbid: {})"
                .format(a_type, error, urlvars.get(a_type, ""),
                    urlvars.get("mbid", "")))

    return name, mbid

def lastfm_autocorrect(scrobble):
    urlvars = {
        "api_key"     : API_KEY,
        "format"      : "json",
        "autocorrect" : 1
    }

    # Artist autocorrect
    vars_artist = urlvars.copy()
    vars_artist["method"] = "artist.getinfo"
    vars_artist["artist"] = scrobble.artist
    if scrobble.artist_mbid:
        vars_artist["mbid"] = scrobble.artist_mbid

    artist, artist_mbid = lastfm_autocorrect_get(vars_artist, "artist")

    # Track autocorrect
    vars_track = urlvars.copy()
    vars_track["method"] = "track.getinfo"
    vars_track["artist"] = artist # Use autocorrected artist
    vars_track["track"] = scrobble.track
    if scrobble.track_mbid:
        vars_track["mbid"] = scrobble.track_mbid

    track, track_mbid = lastfm_autocorrect_get(vars_track, "track")

    # Album autocorrect
    if scrobble.album or scrobble.album_mbid:
        vars_album = urlvars.copy()
        vars_album["method"] = "album.getinfo"
        vars_album["artist"] = artist # Use autocorrected artist
        vars_album["album"] = scrobble.album
        if scrobble.album_mbid:
            vars_album["mbid"] = scrobble.album_mbid

        album, album_mbid = lastfm_autocorrect_get(vars_album, "album")

    # Replace original data with the autocorrected data
    scrobble.artist = artist
    scrobble.artist_mbid = artist_mbid
    scrobble.track = track
    scrobble.track_mbid = track_mbid
    if scrobble.album or scrobble.album_mbid:
        scrobble.album = album
        scrobble.album_mbid = album_mbid

def lastfm_error(json):
    if "message" in json and json["message"]:
        return json["message"]
    else:
        return None

# Get a page of scrobbles from Last.FM
def lastfm_get_scrobbles(username, page, scrobble_type):
    urlvars = {
        "api_key" : API_KEY,
        "format"  : "json",
        "limit"   : 200, # Max limit is 200
        "method"  : "user.get{}".format(scrobble_type),
        "page"    : page,
        "user"    : username
    }

    data = url_get(BASEURL, urlvars)
    response = json.loads(data)

    #print(json.dumps(response, indent=4))
    return response

def lastfm_process_scrobbles(scrobble_page, scrobble_type):
    for scb in scrobble_page[scrobble_type]["track"]:
        try:
            if scb["@attr"]["nowplaying"]:
                continue
        except:
            pass

        # Loved tracks have the text info nested in a "name" tag
        name_tag = "#text" if scrobble_type == "recenttracks" else "name"
        scrobble = Scrobble(
                ts=int(scb["date"]["uts"]),
                artist=scb["artist"][name_tag],
                artist_mbid=scb["artist"]["mbid"],
                track=scb["name"],
                track_mbid=scb["mbid"],
                type=scrobble_type
        )

        # Loved tracks usually don't contain album
        if "album" in scb:
            scrobble.album = scb["album"][name_tag]
            scrobble.album_mbid = scb["album"]["mbid"]

        if args.autocorrect:
            try:
                lastfm_autocorrect(scrobble)
            except Exception as e:
                sys.stderr.write(str(e) + "\n")

        yield scrobble

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
            for scrobble in lastfm_process_scrobbles(res, scrobble_type):
                # Check if the processed track is already in the DB.
                # If so, end the processing, as the remaining tracks
                # were already saved
                if scrobble.ts <= last_ts:
                    end = True
                    print("Found track from the last backup, skipping the rest.")
                    break

                rv = db_save_scrobble(db, scrobble, args.username)
                stored += rv
                processed += 1
                printv("[Scrobble #{}]\n{}\n".format(processed, scrobble))

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
def db_save_scrobble(db, scrobble, username):
    cur = db.cursor()
    cur.execute("INSERT OR IGNORE INTO {}_{} VALUES(?, ?, ?, ?, ?, ?, ?)"
            .format(username, scrobble.type),
            (scrobble.ts, scrobble.artist, scrobble.artist_mbid, scrobble.track,
                scrobble.track_mbid, scrobble.album, scrobble.album_mbid))
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

def _tests():
    scrobble = Scrobble(
        artist="c lekktor",
        track="we are all ready death",
        album_mbid="5cea855b-56ee-3c0d-83b2-629db3b98322",
        ts=0
    )

    print("Before autocorrect:\n{}\n".format(scrobble))
    lastfm_autocorrect(scrobble)
    print("After autocorrect:\n{}".format(scrobble))

    if not scrobble.artist_mbid or not scrobble.track_mbid \
            or not scrobble.album_mbid:
        print("Autocorrect test failed")
        return 1

if __name__ == "__main__":
    if not API_KEY:
        print("Missing API key")
        sys.exit(1)

    parser = argparse.ArgumentParser()
    parser.add_argument("--autocorrect", action="store_true",
            help="autocorrects scrobble data using Last.FM database "
                 "(warning: this is really slow as it requires another "
                 "three API calls)")
    parser.add_argument("-d", "--db", dest="dbname", default="lastfm-backup.db3",
            help="SQLite database name")
    parser.add_argument("--drop", action="store_true",
            help="drop the selected data table before scrobble processing")
    parser.add_argument("--force", action="store_true",
            help="re-download all tracks (don't check for the last stored "
                 "timestamp)")
    parser.add_argument("--tests", action="store_true",
            help="perform some sanity/unit tests")
    parser.add_argument("-u", "--user", dest="username", default=None,
            help="Last.FM user name", required=True)
    parser.add_argument("-v", "--verbose", dest="verbose", action="store_true",
            help="increase verbosity")

    scrobble_types = parser.add_argument_group("Scrobble type")
    scrobble_types.add_argument("-l", "--loved", dest="stypes",
            default=None, help="loved tracks", action="append_const",
            const="lovedtracks")
    scrobble_types.add_argument("-s", "--scrobbles", dest="stypes",
            default=None, help="scrobbles", action="append_const",
            const="recenttracks")

    export_opts = parser.add_argument_group("Export")
    export_opts.add_argument("-e", "--export", dest="export", default=None,
            metavar="FILENAME",
            help="export selected database into a tab-separated text file")
    export_opts.add_argument("--separator", default="\t",
            help="override default column separator (TAB)")

    stats_opts = parser.add_argument_group("Statistics")
    stats_opts.add_argument("--stats", action="store_true",
            help="print statistics for given username/scrobble type combination")

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
    elif args.tests:
        _tests()
    else:
        lastfm_process()
