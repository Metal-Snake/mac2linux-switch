# itunes2Navidrome

- Import ratings, play count and last play date from Apple Music to Navidrome

## Setup
1. Navidrome should have imported the same files as iTunes/Apple Music
2. Ensure you have Python and the necessary libraries installed.
3. You need to change the script for your environment, search for ```ChangeMe``` and make the changes for your setup.
4. Shutdown Navidrome server and make a backup of your .db file!
5. Run the script using the command:
   ```
   python itunes2Navidrome.py
   ```


## Notes
Ensure that the Navidrome database is accessible and the correct database type is specified (sqlite or postgres).
