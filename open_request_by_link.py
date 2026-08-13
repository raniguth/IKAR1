# open_request_by_link.py
# PURPOSE OF THIS FILE:
# This file is the "receiving end" of a link created with the Dashboard's
# "Create a Link to a New Event Request" button. For now (before this app
# is a real website), this is how we can still genuinely test that each
# link only works ONCE: run this file, paste in the token you were given,
# and if - and only if - that token is a real, not-yet-used link, it opens
# a fresh New Event Request form and immediately marks the token as used,
# so it can never be reused again.
#
# Once this app is deployed as a real website, a web server would run this
# exact same check (is this token real? has it been used before?) the
# moment someone clicks the link - the logic here is the same logic that
# would move over directly.

import tkinter as tk  # import the GUI library, nicknamed "tk"
from tkinter import messagebox  # import the pop-up message box part of tkinter
import sqlite3  # import the library that lets Python talk to the SQLite database
import datetime  # import the library that helps us work with dates and times
import subprocess  # import the library that lets us launch another Python file as its own program
import sys  # import the library that tells us which Python program is currently running us

# --- Windows display-scaling fix ---
# On Windows, if a screen is set to a "scaling" setting above 100% (very common
# on laptops), tkinter can render fonts/widgets larger than the pixel sizes we
# actually asked for, unless we tell Windows up front that this program will
# handle its own scaling. Without this, buttons/text can get pushed outside
# the window even though our code sizes everything correctly.
import ctypes  # import the library that lets Python talk directly to Windows system settings
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)  # tell Windows "don't auto-scale me, I'll size things myself"
except Exception:  # this call only exists on Windows - safely do nothing on Mac/Linux
    pass  # no action needed on other operating systems


def get_connection():
    return sqlite3.connect("land_farmer.db")  # open (and return) a fresh connection to our database file


def redeem_token(token):
    # this function checks a token and, if it's valid and unused, marks it used
    # returns True if the token was valid and just got redeemed, False otherwise
    connection = get_connection()  # open a connection
    cursor = connection.cursor()  # create a cursor
    cursor.execute("SELECT used FROM RequestLinks WHERE link_token = ?", (token,))  # look up this exact token
    row = cursor.fetchone()  # get the matching row, or None if the token doesn't exist at all

    if row is None:  # the token doesn't exist in our database at all
        connection.close()  # close the connection
        return False  # not valid

    already_used = row[0]  # 0 means unused, 1 means already used
    if already_used == 1:  # if this token has already been redeemed once before
        connection.close()  # close the connection
        return False  # can't be used again

    used_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # capture exactly when this token gets redeemed
    cursor.execute("UPDATE RequestLinks SET used = 1, used_at = ? WHERE link_token = ?", (used_at, token))  # mark it used
    connection.commit()  # save that permanently
    connection.close()  # close the connection
    return True  # this token was valid, and is now used up


# ---------------------------------------------------------------------------
# GUI SETUP
# ---------------------------------------------------------------------------

window = tk.Tk()  # create the main application window
window.title("Land Farmer - Open Request Link")  # set the window's title bar text
window.geometry("400x180")  # set its size

tk.Label(window, text="Enter your link token:", font=("Arial", 11, "bold")).pack(pady=(20, 5))  # instructions
token_entry = tk.Entry(window, width=40)  # a text box to paste the token into
token_entry.pack(pady=5)  # place it

message_label = tk.Label(window, text="", fg="red", wraplength=350)  # a label for error messages
message_label.pack(pady=10)  # place it


def open_form_clicked():
    token = token_entry.get().strip()  # read the typed/pasted token
    if token == "":  # a token must actually be entered
        message_label.config(text="Please paste your link token first.")  # show an error
        return  # stop here

    if redeem_token(token):  # this checks AND immediately marks the token used, all in one step
        window.destroy()  # close this small window
        subprocess.Popen([sys.executable, "new_request_screen.py"])  # launch the New Event Request form as its own program
    else:  # the token was invalid, or already used before
        message_label.config(text="This link is invalid or has already been used. Please request a new link.")  # explain why


tk.Button(window, text="Open Request Form", command=open_form_clicked, bg="#4CAF50", fg="white",
          font=("Arial", 11, "bold")).pack(pady=10)  # the button that checks the token and opens the form

window.mainloop()  # start the GUI event loop - keeps this window open and responsive until closed
