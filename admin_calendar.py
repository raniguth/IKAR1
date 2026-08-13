# admin_calendar.py
# PURPOSE OF THIS FILE:
# This file gives the admin (you) a way to open Ikalendar directly, without
# going through the New Event Request form. Unlike the customer-facing
# button, this admin version CAN browse back into past weeks, so you can
# review previous bookings too.

import tkinter as tk  # import the GUI library, nicknamed "tk"
import ikalendar  # import our Ikalendar module, so we can open the calendar from this screen

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

window = tk.Tk()  # create the main application window for this launcher
window.title("Land Farmer - Admin Calendar Access")  # set the window's title bar text
window.geometry("400x150")  # set the window size - this is just a small launcher, not the calendar itself

tk.Label(window, text="Land Farmer Admin", font=("Arial", 14, "bold")).pack(pady=(20, 5))  # a heading label

open_button = tk.Button(  # create the button that opens the Ikalendar
    window,
    text="Open Ikalendar",  # the button's label
    font=("Arial", 11),
    bg="#2196F3", fg="white",  # blue background, white text, matching the calendar button style elsewhere
    command=lambda: ikalendar.open_calendar(window, allow_past_weeks=True)  # open the calendar, and allow browsing into past weeks
)
open_button.pack(pady=15)  # place the button with spacing

window.mainloop()  # start the GUI event loop - keeps this launcher window open and responsive until closed
