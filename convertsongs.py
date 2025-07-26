from sys import argv
import sys
import csv
import urllib.parse, urllib.request
import json
from time import sleep
import requests
import os

# Delay (in seconds) to wait between tracks (to avoid getting rate limted) - reduce at own risk
delay = 1

# Checking if the command is correct
if len(argv) > 1 and argv[1]:
    pass
else:
    print('\nCommand usage:\npython3 convertsongs.py yourplaylist.csv\nMore info at https://github.com/therealmarius/Spotify-2-AppleMusic')
    exit()

# Function to get contents of file if it exists
def get_connection_data(f,prompt):
    if os.path.exists(f):
        with open(f,'r') as file:
            return file.read().rstrip('\n')
    else:
            return input(prompt)

def create_apple_music_playlist(session, playlist_name):
    url = "https://amp-api.music.apple.com/v1/me/library/playlists"
    data = {
        'attributes': {
            'name': playlist_name,
            'description': 'A new playlist created via API using Spotify-2-AppleMusic',
        }
    }
    # Test if playlist exists and create it if not
    response = session.get(url)
    if response.status_code == 200:
        for playlist in response.json()['data']:
            if playlist['attributes']['name'] == playlist_name:
                print(f"Playlist {playlist_name} already exists!")
                return playlist['id']
    response = session.post(url, json=data)
    if response.status_code == 201:
        sleep(0.2)
        return response.json()['data'][0]['id']
    elif response.status_code == 400:
        try:
            error_data = response.json()
            for error in error_data.get("errors", []):
                print(f"\nError 400: Bad Request. {error.get('code')}: {error.get('messageForDisplay')}")
                print(f"\n{error.get('title')}: {error.get('detail')}")
        except Exception as e:
            print(f"Error 400: 'Bad Request' while creating playlist {playlist_name}!")
        sys.exit(1)
    elif response.status_code == 401:
        print("\nError 401: Unauthorized. Please refer to the README and check you have entered your Bearer Token, Media-User-Token and session cookies.\n")
        sys.exit(1)
    elif response.status_code == 403:
        print("\nError 403: Forbidden. Please refer to the README and check you have entered your Bearer Token, Media-User-Token and session cookies.\n")
        sys.exit(1)
    else:
        raise Exception(f"Error {response.status_code} while creating playlist {playlist_name}!")
        sys.exit(1)
    
# Getting user's data for the connection
token = get_connection_data("token.dat", "\nPlease enter your Apple Music Authorization (Bearer token):\n")
media_user_token = get_connection_data("media_user_token.dat", "\nPlease enter your media user token:\n")
cookies = get_connection_data("cookies.dat", "\nPlease enter your cookies:\n")
country_code = get_connection_data("country_code.dat", "\nPlease enter the country code (e.g., FR, UK, US etc.): ")

# function to escape apostrophes
def escape_apostrophes(s):
    return s.replace("'", "\\'")

# Function to get the iTunes ID of a song (text based search)
def get_itunes_id(title, artist, album):
    BASE_URL = f"https://itunes.apple.com/search?country={country_code}&media=music&entity=song&limit=5&term="
    # Search the iTunes catalog for a song
    try:
        # Search for the title + artist + album
        url = BASE_URL + urllib.parse.quote(title + " " + artist + " " + album)
        request = urllib.request.Request(url)
        try:
            response = urllib.request.urlopen(request)
        except Exception as e1:
            print(e1)
            if ("SSL: CERTIFICATE_VERIFY_FAILED" in e1):
                print("""
                This issue is likey because of missing certification for macOS.
                Here are the steps to solution:
                1. Open the folder /Applications/Python 3.x (x is the version you are running).
                2. Double click the Install Certificates.command. It will open a terminal and install the certificate.
                3. Rerun this script.
                """)                
            exit(1)
        data = json.loads(response.read().decode('utf-8'))
        # If no result, search for the title + artist
        if data['resultCount'] == 0:
            url = BASE_URL + urllib.parse.quote(title + " " + artist)
            request = urllib.request.Request(url)
            response = urllib.request.urlopen(request)
            data = json.loads(response.read().decode('utf-8'))
            # If no result, search for the title + album
            if data['resultCount'] == 0:
                url = BASE_URL + urllib.parse.quote(title + " " + album)
                request = urllib.request.Request(url)
                response = urllib.request.urlopen(request)
                data = json.loads(response.read().decode('utf-8'))
                # If no result, search for the title
                if data['resultCount'] == 0:
                    url = BASE_URL + urllib.parse.quote(title)
                    request = urllib.request.Request(url)
                    response = urllib.request.urlopen(request)
                    data = json.loads(response.read().decode('utf-8'))
    except Exception as e:
        return print(f"An error occured with the text based search request: {e}")
    
    # Try to match the song with the results
    try:
        response = urllib.request.urlopen(request)
        data = json.loads(response.read().decode('utf-8'))
        
        for each in data['results']:
            #Trying to match with the exact track name, the artist name and the album name
            if each['trackName'].lower() == title.lower() and each['artistName'].lower() == artist.lower() and each['collectionName'].lower() == album.lower():
                return each['trackId']           
            #Trying to match with the exact track name and the artist name
            elif each['trackName'].lower() == title.lower() and each['artistName'].lower() == artist.lower():
                return each['trackId']
            #Trying to match with the exact track name and the album name
            elif each['trackName'].lower() == title.lower() and each['collectionName'].lower() == album.lower():
                return each['trackId']
            #Trying to match with the exact track name and the artist name, in the case artist name are different between Spotify and Apple Music
            elif each['trackName'].lower() == title.lower() and (each["artistName"].lower() in artist.lower() or artist.lower() in each["artistName"].lower()):
                return each['trackId']
            #Trying to match with the exact track name and the album name, in the case album name are different between Spotify and Apple Music
            elif each['trackName'].lower() == title.lower() and (each["collectionName"].lower() in album.lower() or album.lower() in each["collectionName"].lower()):
                return each['trackId']  
            #Trying to match with the exact track name
            elif each['trackName'].lower() == title.lower():
                return each['trackId']        
            #Trying to match with the track name, in the case track name are different between Spotify and Apple Music
            elif title.lower() in each['trackName'] or each['trackName'].lower() in title.lower():
                return each['trackId']
        try:
            #If no result, return the first result
            return data['results'][0]['trackId']
        except:
            #If no result, return None
            return None
    except:
        #The error is handled later in the code
        return None

def match_isrc_to_itunes_id(session, album, album_artist, isrc):
    # Search the Apple Music caralog for a song using the ISRC
    BASE_URL = f"https://amp-api.music.apple.com/v1/catalog/{country_code}/songs?filter[isrc]={isrc}"
    try:
        request = session.get(BASE_URL)
        if request.status_code == 200:
            data = json.loads(request.content.decode('utf-8'))
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
        for each in data['data']:
            isrc_album_name = escape_apostrophes(each['attributes']['albumName'].lower())
            isrc_artist_name = escape_apostrophes(each['attributes']['artistName'].lower())
            isrc_track_name = escape_apostrophes(each['attributes']['name'].lower())
            
            if isrc_album_name == album.lower() and isrc_artist_name == album_artist.lower():
                return each['id']
            elif isrc_album_name == album.lower() and (isrc_artist_name in album_artist.lower() or album_artist.lower() in isrc_artist_name):
                return each['id']
            elif isrc_album_name.startswith(album.lower()[:7]) and isrc_artist_name.startswith(album_artist.lower()[:7]):
                return each['id']
            elif isrc_album_name == album.lower():
                return each['id']
    except:
        return None

def fetch_equivalent_song_id(session, song_id):
    try:
        request = session.get(f"https://amp-api.music.apple.com/v1/catalog/{country_code}/songs?filter[equivalents]={song_id}")
        if request.status_code == 200:
            data = json.loads(request.content.decode('utf-8'))
            return data['data'][0]['id']
        else:
            return song_id
    except:
        return song_id


# Function to add a song to a playlist
def add_song_to_playlist(session, song_id, playlist_id, playlist_track_ids, playlist_name):
    song_id=str(song_id)
    equivalent_song_id = fetch_equivalent_song_id(session, song_id)
    if equivalent_song_id != song_id: 
        print(f"{song_id} switched to equivalent -> {equivalent_song_id}")
        if equivalent_song_id in playlist_track_ids:
            print(f"Song {equivalent_song_id} already in playlist {playlist_name}!\n")
            return "DUPLICATE"
        song_id = equivalent_song_id
    try:   
        request = session.post(f"https://amp-api.music.apple.com/v1/me/library/playlists/{playlist_id}/tracks", json={"data":[{"id":f"{song_id}","type":"songs"}]})
        # Checking if the request is successful
        if request.status_code == 200 or request.status_code == 201 or request.status_code== 204:
            print(f"Song {song_id} added successfully!\n\n")
            return "OK"
        # If not, print the error code
        else: 
            print(f"Error {request.status_code} while adding song {song_id}: {request.reason}\n")
            return "ERROR"
    except:
        print(f"HOST ERROR: Apple Music might have blocked the connection during the add of {song_id}!\nPlease wait a few minutes and try again.\nIf the problem persists, please contact the developer.\n")
        return "ERROR"

def get_playlist_track_ids(session, playlist_id):
    # test if song is already in playlist
    try:
        response = session.get(f"https://amp-api.music.apple.com/v1/me/library/playlists/{playlist_id}/tracks")
        if response.status_code == 200:
            #print(response.json()['data'])
            return [track['attributes']['playParams']['catalogId'] for track in response.json()['data']]
        elif response.status_code == 404:
            return []
        else:
            raise Exception(f"Error {response.status_code} while getting playlist {playlist_id}!")
            return None
    except:
        raise Exception(f"Error while getting playlist {playlist_id}!")
        return None
# Opening session
def create_playlist_and_add_song(file):
    with requests.Session() as s:
        s.headers.update({
                    "Authorization": f"{token}",
                    "media-user-token": f"{media_user_token}",
                    "Cookie": f"{cookies}".encode('utf-8'),
                    "Host": "amp-api.music.apple.com",
                    "Accept-Encoding":"gzip, deflate, br",
                    "Referer": "https://music.apple.com/",
                    "Origin": "https://music.apple.com",
                    #"Content-Length": "45",
                    "Connection": "keep-alive",
                    "Sec-Fetch-Dest": "empty",
                    "Sec-Fetch-Mode": "cors",
                    "Sec-Fetch-Site": "same-site",
                    #"TE": "trailers"
                    })
    
    # Getting the playlist name
    playlist_name = os.path.basename(file)
    playlist_name = playlist_name.split('.')
    playlist_name = playlist_name[0]
    playlist_name = playlist_name.replace('_', ' ')
    playlist_name = playlist_name.capitalize()

    playlist_identifier = create_apple_music_playlist(s, playlist_name)

    playlist_track_ids = get_playlist_track_ids(s, playlist_identifier)
    #print(playlist_track_ids)
    
    # Opening the inputed CSV file
    with open(str(file), encoding='utf-8') as file:
        file = csv.reader(file)
        header_row = next(file)
        if header_row[1] != 'Track Name' or header_row[3] != 'Artist Name(s)' or header_row[5] != 'Album Name' or header_row[16] != 'ISRC':
            print('\nThe CSV file is not in the correct format!\nPlease be sure to download the CSV file(s) only from https://watsonbox.github.io/exportify/.\n\n')
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
            title, artist, album, album_artist, isrc = escape_apostrophes(
                row[1]), escape_apostrophes(row[3]), escape_apostrophes(row[5]), escape_apostrophes(row[7]), escape_apostrophes(row[16])
            track_id = match_isrc_to_itunes_id(s, album, album_artist, isrc)
            if track_id:
                isrc_based += 1
            else:
                print(f'No result found for {title} | {artist} | {album} with {isrc}. Trying text based search...')
                track_id = get_itunes_id(title, artist, album)
                if track_id:
                    text_based += 1
            # If the song is found, add it to the playlist
            if track_id:
                if str(track_id) in playlist_track_ids:
                    print(f'N°{n} | {title} | {artist} | {album} => {track_id}')
                    print(f"Song {track_id} already in playlist {playlist_name}!\n")
                    failed += 1
                    continue
                print(f'N°{n} | {title} | {artist} | {album} => {track_id}')
                if delay >= 0.5:
                    sleep(delay)
                else:
                    sleep(0.5)
                result = add_song_to_playlist(s, track_id, playlist_identifier, playlist_track_ids, playlist_name)
                if result == "OK": converted += 1
                elif result == "ERROR":
                    with open(f'{playlist_name}_noresult.txt', 'a+', encoding='utf-8') as f:
                        f.write(f'{title} | {artist} | {album} => UNABLE TO ADD TO PLAYLIST\n')
                        f.write('\n')
                    failed += 1
                elif result == "DUPLICATE": failed += 1
            # If not, write it in a file
            else:
                print(f'N°{n} | {title} | {artist} | {album} => NOT FOUND\n')
                with open(f'{playlist_name}_noresult.txt', 'a+', encoding='utf-8') as f:
                    f.write(f'{title} | {artist} | {album} => NOT FOUND\n')
                    f.write('\n')
                failed += 1
            sleep(delay)
    # Printing the stats report
    converted_percentage = round(converted / n * 100) if n > 0 else 100
    print(f'\n - STAT REPORT -\nPlaylist Songs: {n}\nConverted Songs: {converted}\nFailed Songs: {failed}\nPlaylist converted at {converted_percentage}%\n\nConverted using ISRC: {isrc_based}\nConverted using text based search: {text_based}\n\n')


if __name__ == "__main__":
    if len(argv) > 1 and argv[1]:
        if ".csv" in argv[1]:
            create_playlist_and_add_song(argv[1])
        else:
            # get all csv files in the directory argv[1]
            files = [f for f in os.listdir(argv[1]) if os.path.isfile(os.path.join(argv[1], f))]
            # loop through all csv files
            for file in files:
                if ".csv" in file:
                    create_playlist_and_add_song(os.path.join(argv[1], file))

# Developed by @therealmarius on GitHub
# Based on the work of @simonschellaert on GitHub
# Based on the work of @nf1973 on GitHub
# Github project page: https://github.com/therealmarius/Spotify-2-AppleMusic