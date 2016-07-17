<?php

function curl_get($url) {
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url);
    curl_setopt($ch, CURLOPT_TIMEOUT, 5);
    curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 5);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    $data = curl_exec($ch);
    curl_close($ch);

    return $data;
}

function lastfm_get_nowplaying($user) {
    $lastfm_key = "ENTER_VALID_LASTFM_KEY";
    $api_url = "https://ws.audioscrobbler.com/2.0/?method=user.getrecenttracks"
             . "&api_key=$lastfm_key&format=json&limit=1";
    $url = $api_url . "&user=" . urlencode($user);
    $data = curl_get($url);

    if($data === false) {
        echo "Couldn't get user data\n";
        die;
    }

    try {
        $json = json_decode($data, true);
        #echo "<pre>" . json_encode($json, JSON_PRETTY_PRINT) . "</pre>";
        $current = $json["recenttracks"]["track"][0];
        if(!$current["@attr"]["nowplaying"]) {
            echo "No current track for user $user\n";
            return false;
        }

        $artist = $current["artist"]["#text"];
        $track = $current["name"];
        return array($artist, $track);
    } catch (\Exception $e) {
        echo "Exception: " . $e . "\n";
    }

    return false;
}

function get_lyrics($artist, $track) {
    $base_url = "https://makeitpersonal.co/lyrics";
    $artist = urlencode($artist);
    $track = urlencode($track);
    $url = $base_url . "?artist=$artist&title=$track";
    $data = curl_get($url);

    return trim($data);
}

if(PHP_SAPI === "cli") {
    $username = ($argc > 1) ? $argv[1] : "";
} else {
    $username = isset($_GET["username"]) ? $_GET["username"] : "";
}

if(empty($username)) {
    echo "Missing last.fm username\n";
    die;
}

$track = lastfm_get_nowplaying($username);
if($track === false) {
    die;
}

if(PHP_SAPI !== "cli") echo "<pre>\n";
echo $track[0] . " - " . $track[1] . "\n\n";
echo get_lyrics($track[0], $track[1]) . "\n";
if(PHP_SAPI !== "cli") echo "</pre>";

?>
