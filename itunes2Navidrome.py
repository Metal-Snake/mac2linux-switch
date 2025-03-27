import locale
import sqlite3
import os
import subprocess
#import psycopg
import logging
from typing import List, Tuple
from datetime import datetime
import unicodedata

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


def extract_ratings_from_applescript() -> List[Tuple[str, int, str, int]]:
    logging.debug("Extracting ratings from Apple Music via AppleScript...")
    script = '''
    tell application "Music"
        set track_list to {}
        set max_tracks to 10  -- Max number of tracks, good for testing, uncomment 4 lines below
        set track_counter to 0
        repeat with t in tracks of library playlist 1
            --if track_counter < max_tracks then
                try
                    set track_location to location of t as text
                    set track_rating to rating of t
                    set track_played_date to played date of t
                    set track_play_count to played count of t
                    set end of track_list to (track_location & "||" & track_rating & "||" & track_played_date & "||" & track_play_count)
                    set track_counter to track_counter + 1
                on error errMsg
                    log "Error processing track: " & errMsg
                end try
            --else
            --    exit repeat
            --end if
        end repeat
        return track_list
    end tell
    '''
    
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    logging.debug(f"AppleScript output: {result.stdout}")
    logging.debug(f"AppleScript errors: {result.stderr}")
    
    ratings = []
    try:
        # ChangeME - set your locale, based on what iTunes/Music.app sends as datetime format
        locale.setlocale(locale.LC_TIME, 'de_DE.UTF-8')  # Set the locale to German (Germany)
    except locale.Error as e:
        logging.error(f"Could not set locale: {e}")
    
    if result.returncode == 0 and result.stdout.strip():
        logging.debug(f"result: {result.stdout.strip()}")
        # ChangeME - The split needs more than just the comma because of the date format in the data from iTunes
        lines = result.stdout.strip().split(", Pluto:") 
        for line in lines:
            parts = line.split("||")
            if len(parts) == 4 and parts[1].isdigit() and parts[3].isdigit():
                try:
                    play_date = parts[2] if parts[2] != "missing value" else None
                    if play_date:
                        try:
                            logging.debug(f"parsing date for track {parts[0]}: {play_date} ---- {parts}")
                            play_date = datetime.strptime(play_date, "%A, %d. %B %Y um %H:%M:%S")  # Example: Freitag, 6. Juli 2018 um 22:31:45
                            play_date = play_date.isoformat()  # Standard ISO-Datetime
                        except ValueError:
                            logging.error(f"Error parsing date for track {parts[0]}: {play_date} Invalid format")
                            play_date = None
                    ratings.append((parts[0], int(parts[1]) // 20, play_date, int(parts[3])))
                except Exception as e:
                    logging.error(f"Error parsing rating for track {parts[0]}: {e}")
                    continue
    else:
        logging.error("AppleScript returned no data or an error occurred.")
    
    logging.info(f"Extracted {len(ratings)} ratings from Apple Music.")
    
    # Save ratings to a file
    with open("ratings_data.txt", "w") as file:
        for rating in ratings:
            file.write("||".join(map(str, rating)) + "\n")
    
    return ratings


def read_ratings_from_file(file_path: str) -> List[Tuple[str, int, str, int]]:
    ratings = []
    with open(file_path, "r") as file:
        for line in file:
            parts = line.strip().split("||")
            if len(parts) == 4:
                ratings.append((parts[0], int(parts[1]), parts[2], int(parts[3])))
    return ratings


def insert_ratings_into_navidrome(db_path: str, ratings: List[Tuple[str, int, str, int]], db_type: str = "sqlite", user_id: str = "1"):
    logging.debug("Connecting to Navidrome database...")
    if db_type == "sqlite":
        conn = sqlite3.connect(db_path)
    #elif db_type == "postgres":
    #    conn = psycopg.connect(db_path)
    else:
        raise ValueError("Unsupported database type")
    
    cursor = conn.cursor()
    for file_path, rating, play_date, play_count in ratings:
        #logging.debug(f"Processing file: {file_path} with rating: {rating}, play_date: {play_date}, and play_count: {play_count}")
        file_path = file_path.replace("Pluto:iTunes 2017:Music:", "") # ChangeME For the first record
        file_path = file_path.replace("iTunes 2017:Music:", "")  # ChangeME All other records are missing part of the part because of the split above
        file_path = file_path.replace(":", "/") # ChangeME Path separator in macOS is colon, this needs to be replaced with the slash
        
        file_path_nfc = unicodedata.normalize('NFC', file_path)
        file_path_nfd = unicodedata.normalize('NFD', file_path)
        cursor.execute("""
            SELECT id FROM media_file WHERE path LIKE ? OR path LIKE ? OR path LIKE ?
        """, (f"%{file_path}%", f"%{file_path_nfd}%", f"%{file_path_nfc}%"))
        result = cursor.fetchone()
        
        if result:
            item_id = result[0]
            cursor.execute("""
                INSERT INTO annotation (user_id, item_id, item_type, rating, play_date, play_count)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, item_id, item_type) DO UPDATE SET
                    rating = CASE WHEN annotation.rating = 0 THEN EXCLUDED.rating ELSE annotation.rating END,
                    play_date = CASE WHEN annotation.play_date IS NULL OR EXCLUDED.play_date > annotation.play_date THEN EXCLUDED.play_date ELSE annotation.play_date END,
                    play_count = CASE WHEN EXCLUDED.play_count > annotation.play_count THEN EXCLUDED.play_count ELSE annotation.play_count END
            """, (user_id, item_id, "media_file", rating, play_date, play_count))
        else:
            logging.warning(f"No match found in media_file for {file_path}")
    
    conn.commit()
    conn.close()
    logging.info("Database update complete.")




if __name__ == "__main__":
    navidrome_db = "/Users/metalsnake/Desktop/navidrome.db"  # ChangeME
    user_id = ""  # ChangeME - User-ID in Navidrome - check your navidrome.db for your user-id
    db_type = "sqlite"  # Or "postgres" - not tested!
    
    # Read ratings from file if it exists, otherwise extract from Apple Music
    if os.path.exists("ratings_data.txt"):
        ratings = read_ratings_from_file("ratings_data.txt")
    else:
        ratings = extract_ratings_from_applescript()
    insert_ratings_into_navidrome(navidrome_db, ratings, db_type, user_id)
