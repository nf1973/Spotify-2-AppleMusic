from sys import argv
import sys
import csv
import urllib.parse, urllib.request
import json
from time import sleep
import requests
import os
from ratelimit import limits
from bs4 import BeautifulSoup
import dateparser

# Delay (in seconds) to wait between tracks (to avoid getting rate limted) - reduce at own risk
delay = 1

# Checking if the command is correct
if len(argv) > 1 and argv[1]:
    pass
else:
    print(
        "\nCommand usage:\npython3 convertsongs.py yourplaylist.csv\nMore info at https://github.com/therealmarius/Spotify-2-AppleMusic"
    )
    exit()


# Function to get contents of file if it exists
def get_connection_data(f, prompt):
    if os.path.exists(f):
        with open(f, "r") as file:
            return file.read().rstrip("\n")
    else:
        return input(prompt)


def create_apple_music_playlist(session, playlist_name):
    url = "https://amp-api.music.apple.com/v1/me/library/playlists"
    data = {
        "attributes": {
            "name": playlist_name,
            "description": "A new playlist created via API using Spotify-2-AppleMusic",
        }
    }
    # Test if playlist exists and create it if not
    response = session.get(url)
    if response.status_code == 200:
        for playlist in response.json()["data"]:
            if playlist["attributes"]["name"] == playlist_name:
                print(f"Playlist {playlist_name} already exists!")
                return playlist["id"]
    response = session.post(url, json=data)
    if response.status_code == 201:
        sleep(0.2)
        return response.json()["data"][0]["id"]
    elif response.status_code == 401:
        print(
            "\nError 401: Unauthorized. Please refer to the README and check you have entered your Bearer Token, Media-User-Token and session cookies.\n"
        )
        sys.exit(1)
    elif response.status_code == 403:
        print(
            "\nError 403: Forbidden. Please refer to the README and check you have entered your Bearer Token, Media-User-Token and session cookies.\n"
        )
        sys.exit(1)
    else:
        raise Exception(
            f"Error {response.status_code} while creating playlist {playlist_name}!"
        )
        sys.exit(1)


# Getting user's data for the connection
token = get_connection_data(
    "token.dat", "\nPlease enter your Apple Music Authorization (Bearer token):\n"
)
media_user_token = get_connection_data(
    "media_user_token.dat", "\nPlease enter your media user token:\n"
)
cookies = get_connection_data("cookies.dat", "\nPlease enter your cookies:\n")
country_code = get_connection_data(
    "country_code.dat", "\nPlease enter the country code (e.g., FR, UK, US etc.): "
)


# apple limit is 20 calls per minute
@limits(calls=19, period=1)
def call_api(url: str) -> json:
    for _ in range(3):
        req = requests.get(url)
        if req.status_code == 200:
            return req.json()
        else:
            print("Error {req.status_code} while calling API, retrying...")
    raise Exception(f"Error {req.status_code} while calling API {url}!")


def verify_release_date(item: json, date: str) -> bool:
    req = requests.get(item["trackViewUrl"])
    if req.status_code != 200:
        return False
    soup = BeautifulSoup(req.text, "html.parser")
    element = soup.find("p", {"data-testid": "tracklist-footer-description"})
    if not element:
        return False
    date_strs = element.text.split("\n")
    if len(date_strs) == 0:
        return
    # fetch the release date from the tracklist-footer-description
    return dateparser.parse(date_strs[0]) == dateparser.parse(date)


def try_to_match(url, title, artist, album, date) -> str | None:
    try:
        data = call_api(url)
    except Exception as e1:
        print(e1)
        if e1 is str and "SSL: CERTIFICATE_VERIFY_FAILED" in e1:
            print(
                """
            This issue is likely because of missing certification for macOS.
            Here are the steps to solution:
            1. Open the folder /Applications/Python 3.x (x is the version you are running).
            2. Double click the Install Certificates.command. It will open a terminal and install the certificate.
            3. Rerun this script.
            """
            )
        exit(1)

    for each in data["results"]:
        if (
            # Trying to match with the exact track name, the artist name and the album name
            (
                each["trackName"].lower() == title.lower()
                and each["artistName"].lower() == artist.lower()
                and each["collectionName"].lower() == album.lower()
            )
            # Trying to match with the release date, this is another accurate way.
            # It's really rare to have the same release date for two different songs with the same information.
            or verify_release_date(each, date)
            # Trying to match with the exact track name and the artist name
            or (
                each["trackName"].lower() == title.lower()
                and each["artistName"].lower() == artist.lower()
            )
            # Trying to match with the exact track name and the artist name, in the case artist name are different between Spotify and Apple Music
            or (
                each["trackName"].lower() == title.lower()
                and (
                    each["artistName"].lower().replace(" ", "")
                    in artist.lower().replace(" ", "")
                    or artist.lower().replace(" ", "")
                    in each["artistName"].lower().replace(" ", "")
                )
            )
            # Trying to match with the exact artist name and the track name, in the case track name are different between Spotify and Apple Music
            or (
                each["artistName"].lower() == title.lower()
                and (
                    each["trackName"].lower().replace(" ", "")
                    in artist.lower().replace(" ", "")
                    or artist.lower().replace(" ", "")
                    in each["trackName"].lower().replace(" ", "")
                )
            )
            # this condition is too loosen in my tries, it will allow wrong matches,
            # then I need to surface through my playlist to check if there exists any wrong matches
            # # Trying to match with the exact track name and the album name
            # or (
            #     each["trackName"].lower() == title.lower()
            #     and each["collectionName"].lower() == album.lower()
            # )
        ):
            return each["trackId"]

    return None


# function to escape apostrophes
def escape_apostrophes(s):
    return s.replace("'", "\\'")


# Function to get the iTunes ID of a song (text based search)
def get_itunes_id(title, artist, album, date):
    # ref: https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/iTuneSearchAPI/Searching.html
    BASE_URL = f"https://itunes.apple.com/search?country={country_code}&media=music&entity=song&limit=15&term={urllib.parse.quote(title)}"
    ARTIST_TERM = f"&artistTerm={urllib.parse.quote(artist)}"
    ALBUM_TERM = f"&albumTerm={urllib.parse.quote(album)}"

    # Search the iTunes catalog for a song
    try:
        # Search for the title + artist + album
        re = try_to_match(
            BASE_URL + ARTIST_TERM + ALBUM_TERM, title, artist, album, date
        )
        # If no result, search for the title + artist
        if re is None:
            re = try_to_match(BASE_URL + ARTIST_TERM, title, artist, album, date)
            # If no result, search for the title + album
            if re is None:
                re = try_to_match(BASE_URL + ALBUM_TERM, title, artist, album, date)
                # If no result, search for the title
                if re is None:
                    re = try_to_match(BASE_URL, title, artist, album, date)
    except Exception as e:
        print(f"An error occurred with the text based search request: {e}")
        raise e
    return re


def match_isrc_to_itunes_id(session, album, album_artist, isrc):
    # Search the Apple Music catalog for a song using the ISRC
    BASE_URL = f"https://amp-api.music.apple.com/v1/catalog/{country_code}/songs?filter[isrc]={isrc}"
    try:
        request = session.get(BASE_URL)
        if request.status_code == 200:
            data = json.loads(request.content.decode("utf-8"))
        else:
            raise Exception(f"Error {request.status_code}\n{request.reason}\n")
        if data["data"]:
            pass
        else:
            return None
    except Exception as e:
        return print(f"An error occured with the ISRC based search request: {e}")

    # Try to match the song with the results
    try:
        for each in data["data"]:
            isrc_album_name = escape_apostrophes(
                each["attributes"]["albumName"].lower()
            )
            isrc_artist_name = escape_apostrophes(
                each["attributes"]["artistName"].lower()
            )
            # isrc_track_name = escape_apostrophes(each["attributes"]["name"].lower())

            if (
                isrc_album_name == album.lower()
                and isrc_artist_name == album_artist.lower()
            ):
                return each["id"]
            elif isrc_album_name == album.lower() and (
                isrc_artist_name in album_artist.lower()
                or album_artist.lower() in isrc_artist_name
            ):
                return each["id"]
            elif isrc_album_name.startswith(
                album.lower()[:7]
            ) and isrc_artist_name.startswith(album_artist.lower()[:7]):
                return each["id"]
            elif isrc_album_name == album.lower():
                return each["id"]
    except:
        return None


def fetch_equivalent_song_id(session, song_id):
    try:
        request = session.get(
            f"https://amp-api.music.apple.com/v1/catalog/{country_code}/songs?filter[equivalents]={song_id}"
        )
        if request.status_code == 200:
            return json.loads(request.content.decode("utf-8"))["data"][0]["id"]
        else:
            return song_id
    except:
        return song_id


# Function to add a song to a playlist
def add_song_to_playlist(
    session, song_id, playlist_id, playlist_track_ids, playlist_name
):
    song_id = str(song_id)
    equivalent_song_id = fetch_equivalent_song_id(session, song_id)
    if equivalent_song_id != song_id:
        print(f"{song_id} switched to equivalent -> {equivalent_song_id}")
        if equivalent_song_id in playlist_track_ids:
            print(f"Song {equivalent_song_id} already in playlist {playlist_name}!\n")
            return "DUPLICATE"
        song_id = equivalent_song_id
    try:
        request = session.post(
            f"https://amp-api.music.apple.com/v1/me/library/playlists/{playlist_id}/tracks",
            json={"data": [{"id": f"{song_id}", "type": "songs"}]},
        )
        # Checking if the request is successful
        if (
            request.status_code == 200
            or request.status_code == 201
            or request.status_code == 204
        ):
            print(f"Song {song_id} added successfully!\n\n")
            return "OK"
        # If not, print the error code
        else:
            print(
                f"Error {request.status_code} while adding song {song_id}: {request.reason}\n"
            )
            return "ERROR"
    except:
        print(
            f"HOST ERROR: Apple Music might have blocked the connection during the add of {song_id}!\nPlease wait a few minutes and try again.\nIf the problem persists, please contact the developer.\n"
        )
        return "ERROR"


def get_playlist_track_ids(session, playlist_id):
    # test if song is already in playlist
    try:
        response = session.get(
            f"https://amp-api.music.apple.com/v1/me/library/playlists/{playlist_id}/tracks"
        )
        if response.status_code == 200:
            # print(response.json()['data'])
            return [
                track["attributes"]["playParams"]["catalogId"]
                for track in response.json()["data"]
            ]
        elif response.status_code == 404:
            return []
        else:
            raise Exception(
                f"Error {response.status_code} while getting playlist {playlist_id}!"
            )
            return None
    except:
        raise Exception(f"Error while getting playlist {playlist_id}!")
        return None


# Opening session
def create_playlist_and_add_song(file):
    with requests.Session() as s:
        s.headers.update(
            {
                "Authorization": f"{token}",
                "media-user-token": f"{media_user_token}",
                "Cookie": f"{cookies}".encode("utf-8"),
                "Host": "amp-api.music.apple.com",
                "Accept-Encoding": "gzip, deflate, br",
                "Referer": "https://music.apple.com/",
                "Origin": "https://music.apple.com",
                # "Content-Length": "45",
                "Connection": "keep-alive",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-site",
                # "TE": "trailers"
                # from https://www.useragents.me/
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.3",
            }
        )

    # Getting the playlist name
    playlist_name: str = os.path.basename(file)
    playlist_name = playlist_name.split(".")
    playlist_name = playlist_name[0]
    playlist_name = playlist_name.replace("_", " ")
    playlist_name = playlist_name.capitalize()

    playlist_identifier = create_apple_music_playlist(s, playlist_name)

    playlist_track_ids: list = get_playlist_track_ids(s, playlist_identifier)
    # print(playlist_track_ids)

    # Opening the inputed CSV file
    with open(str(file), encoding="utf-8") as file:
        file = csv.reader(file)
        header_row = next(file)
        if (
            header_row[1] != "Track Name"
            or header_row[3] != "Artist Name(s)"
            or header_row[5] != "Album Name"
            or header_row[16] != "ISRC"
        ):
            print(
                "\nThe CSV file is not in the correct format!\nPlease be sure to download the CSV file(s) only from https://watsonbox.github.io/exportify/.\n\n"
            )
            return
        # Initializing variables for the stats
        n = 0
        isrc_based = 0
        text_based = 0
        converted = 0
        failed = 0
        # Looping through the CSV file
        for row in file:
            n += 1
            # Trying to get the iTunes ID of the song
            title, artist, album, album_artist, date, isrc = (
                escape_apostrophes(row[1]),
                escape_apostrophes(row[3]),
                escape_apostrophes(row[5]),
                escape_apostrophes(row[7]),
                escape_apostrophes(row[8]),
                escape_apostrophes(row[16]),
            )
            track_id = match_isrc_to_itunes_id(s, album, album_artist, isrc)
            if track_id:
                isrc_based += 1
            else:
                print(
                    f"No result found for {title} | {artist} | {album} | {date} with {isrc}. Trying text based search..."
                )
                track_id = get_itunes_id(title, artist, album, date)
                if track_id:
                    text_based += 1
            # If the song is found, add it to the playlist
            if track_id:
                print(f"N°{n} | {title} | {artist} | {album} => {track_id}")
                if str(track_id) in playlist_track_ids:
                    print(f"Song {track_id} already in playlist {playlist_name}!\n")
                    failed += 1
                    continue
                if delay >= 0.5:
                    sleep(delay)
                else:
                    sleep(0.5)
                result = add_song_to_playlist(
                    s, track_id, playlist_identifier, playlist_track_ids, playlist_name
                )
                if result == "OK":
                    converted += 1
                elif result == "ERROR":
                    with open(
                        f"{playlist_name}_noresult.txt", "a+", encoding="utf-8"
                    ) as f:
                        f.write(
                            f"{title} | {artist} | {album} => UNABLE TO ADD TO PLAYLIST\n"
                        )
                        f.write("\n")
                    failed += 1
                elif result == "DUPLICATE":
                    failed += 1
            # If not, write it in a file
            else:
                print(f"N°{n} | {title} | {artist} | {album} => NOT FOUND\n")
                with open(f"{playlist_name}_noresult.txt", "a+", encoding="utf-8") as f:
                    f.write(f"{title} | {artist} | {album} => NOT FOUND\n")
                    f.write("\n")
                failed += 1
            sleep(delay)
    # Printing the stats report
    converted_percentage = round(converted / n * 100) if n > 0 else 100
    print(
        f"\n - STAT REPORT -\nPlaylist Songs: {n}\nConverted Songs: {converted}\nFailed Songs: {failed}\nPlaylist converted at {converted_percentage}%\n\nConverted using ISRC: {isrc_based}\nConverted using text based search: {text_based}\n\n"
    )


if __name__ == "__main__":
    if len(argv) > 1 and argv[1]:
        if ".csv" in argv[1]:
            create_playlist_and_add_song(argv[1])
        else:
            # get all csv files in the directory argv[1]
            files = [
                f
                for f in os.listdir(argv[1])
                if os.path.isfile(os.path.join(argv[1], f))
            ]
            # loop through all csv files
            for file in files:
                if ".csv" in file:
                    create_playlist_and_add_song(os.path.join(argv[1], file))

# Developed by @therealmarius on GitHub
# Based on the work of @simonschellaert on GitHub
# Based on the work of @nf1973 on GitHub
# Github project page: https://github.com/therealmarius/Spotify-2-AppleMusic
