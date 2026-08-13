# new_request_screen.py
# PURPOSE OF THIS FILE:
# This file shows a window (GUI) where you type in a new customer inquiry -
# the customer's details plus what they're asking for (date, time, guests, etc).
# When you click "Build Your Menu", it checks that required fields are filled in,
# checks whether the restaurant has room for that many guests at that date/time,
# saves the request into land_farmer.db, and then opens the menu-building screen
# so the client can choose their meal and get an instant quote.

import tkinter as tk  # import the GUI library, and nickname it "tk" so we type less
from tkinter import messagebox  # import the pop-up message box part of tkinter (for warnings/errors)
import sqlite3  # import the library that lets Python talk to the SQLite database
import datetime  # import the library that helps us work with dates and times
import ikalendar  # import our Ikalendar module, so we can open the availability calendar from this screen
import build_your_menu  # import our Build Your Menu module, so we can open the menu builder from this screen

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
import date_picker  # import our date picker module, for the clickable monthly calendar

# ---------------------------------------------------------------------------
# DATABASE HELPER FUNCTIONS
# These functions do the actual database work, separate from the GUI code
# ---------------------------------------------------------------------------

def get_opening_hours_for_date(cursor, date_obj):
    # this function looks up the open/close time for whatever day-of-week a given date falls on
    day_name = date_obj.strftime("%A")  # convert the date into its weekday name, e.g. "Wednesday"
    cursor.execute("SELECT open_time, close_time FROM OpeningHours WHERE day_of_week = ?", (day_name,))  # look up that day's hours
    row = cursor.fetchone()  # fetchone() gets the single matching row, or None if somehow not found
    return row if row is not None else (None, None)  # return the (open_time, close_time) pair, or (None, None) if missing


def check_capacity(cursor, event_date, start_time, end_time, num_guests):
    # this function figures out how many guests are already booked at an overlapping time,
    # and whether adding this new request would go over the restaurant's total capacity
    cursor.execute("""
        SELECT SUM(num_guests) FROM Events
        WHERE event_date = ?
        AND event_start_time < ?
        AND event_end_time > ?
    """, (event_date, end_time, start_time))  # find CONFIRMED events on the same date that overlap our time range
    result = cursor.fetchone()[0]  # fetchone() gets the single row of the result, [0] gets the first column (the sum)
    already_booked = result if result is not None else 0  # if there are no matching events, SUM returns None, so treat that as 0
    cursor.execute("SELECT total_capacity FROM Settings LIMIT 1")  # get the restaurant's total capacity from Settings
    total_capacity = cursor.fetchone()[0]  # extract the number from the result
    total_after_this_request = already_booked + num_guests  # calculate what the total would be if we add this request
    return already_booked, total_capacity, total_after_this_request  # send back all 3 numbers so the GUI can use them


def find_or_create_customer(cursor, first_name, last_name, id_number, company_name, company_id_number, phone, email):
    # this function checks if a customer with this id_number already exists;
    # if so, it reuses that customer instead of creating a duplicate
    cursor.execute("SELECT customer_id FROM Customers WHERE id_number = ?", (id_number,))  # look for a matching id_number
    existing = cursor.fetchone()  # fetchone() returns None if nothing was found, or the row if it was
    if existing is not None:  # if we found an existing customer with this id_number
        return existing[0]  # return their existing customer_id, [0] pulls the id out of the row
    else:  # otherwise, this is a brand new customer
        cursor.execute("""
            INSERT INTO Customers (first_name, last_name, id_number, company_name, company_id_number, phone, email)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (first_name, last_name, id_number, company_name, company_id_number, phone, email))  # insert the new customer
        return cursor.lastrowid  # lastrowid gives us the customer_id that SQLite just auto-generated


def save_request(customer_id, event_date, start_time, end_time, num_guests, event_type,
                  dietary_restrictions, special_requests, notes):
    # this function saves the actual Request row into the database, and returns its new request_number
    connection = sqlite3.connect("land_farmer.db")  # open a connection to the database file
    cursor = connection.cursor()  # create a cursor to run commands with
    today = datetime.date.today().isoformat()  # get today's date as text, e.g. "2026-07-21"
    cursor.execute("""
        INSERT INTO Requests (customer_id, request_date, requested_event_date, requested_start_time,
                               requested_end_time, num_guests, event_type, dietary_restrictions,
                               special_requests, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (customer_id, today, event_date, start_time, end_time, num_guests, event_type,
          dietary_restrictions, special_requests, notes))  # insert the request row (status defaults to 'New Inquiry')
    new_request_number = cursor.lastrowid  # lastrowid gives us the request_number SQLite just auto-generated
    connection.commit()  # commit() permanently saves our changes to the database file
    connection.close()  # close the connection since we're done with it
    return new_request_number  # give back the new request_number so the caller can open the menu builder for it


# ---------------------------------------------------------------------------
# GUI SETUP
# Build the window and all its fields
# ---------------------------------------------------------------------------

window = tk.Tk()  # create the main application window
window.title("Land Farmer - New Event Request")  # set the text shown in the window's title bar
window.geometry("520x650")  # set the STARTING window size in pixels: width x height (the scrollbar handles the rest)

# ---------------------------------------------------------------------------
# SCROLLABLE CONTAINER
# Since this form has many fields, it may be taller than the window itself.
# A Canvas + Scrollbar lets the user scroll down to see every field and button,
# no matter how small their screen is.
# ---------------------------------------------------------------------------

canvas = tk.Canvas(window)  # a Canvas is a scrollable drawing surface - we'll put our form inside it
scrollbar = tk.Scrollbar(window, orient="vertical", command=canvas.yview)  # a vertical scrollbar linked to the canvas
form_frame = tk.Frame(canvas)  # a Frame is an invisible container - this one will hold all our labels/entries/buttons

# whenever the form_frame changes size (e.g. we add more fields), update the canvas's scrollable area
form_frame.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))

canvas.create_window((0, 0), window=form_frame, anchor="nw")  # place form_frame inside the canvas, starting top-left
canvas.configure(yscrollcommand=scrollbar.set)  # connect the canvas's vertical position to the scrollbar

canvas.pack(side="left", fill="both", expand=True)  # place the canvas on the left, filling all available space
scrollbar.pack(side="right", fill="y")  # place the scrollbar on the right, filling the full height

def on_mousewheel(event):
    canvas.yview_scroll(-1 * (event.delta // 120), "units")  # scroll the canvas up/down when the mouse wheel is used

canvas.bind_all("<MouseWheel>", on_mousewheel)  # activate mouse wheel scrolling anywhere over the window

tk.Label(form_frame, text="New Event Request", font=("Arial", 16, "bold")).pack(pady=10)  # a big heading label at the top

# a small helper function to build a "Label + Entry box" pair quickly, since we need many of them
def add_field(label_text, required):
    display_text = label_text + (" *" if required else "")  # add a * to the label if the field is required
    tk.Label(form_frame, text=display_text).pack(anchor="w", padx=20)  # show the label, left-aligned, with some left padding
    entry = tk.Entry(form_frame, width=40)  # create a text box for the user to type into
    entry.pack(padx=20, pady=(0, 8))  # place the text box below the label, with a little spacing after it
    return entry  # give back the entry box so we can read its value later

tk.Label(form_frame, text="Customer Details", font=("Arial", 12, "underline")).pack(anchor="w", padx=20, pady=(10, 0))  # section heading

first_name_entry = add_field("First Name", True)  # required field for first name
last_name_entry = add_field("Last Name", True)  # required field for last name
id_number_entry = add_field("ID Number", True)  # required field for ID number
company_name_entry = add_field("Company Name", False)  # optional field for company name
company_id_entry = add_field("Company ID Number", False)  # optional field for company ID number
phone_entry = add_field("Phone (e.g. 0501234567)", True)  # required field for phone, with an example format shown
email_entry = add_field("Email", True)  # required field for email

tk.Label(form_frame, text="Event Details", font=("Arial", 12, "underline")).pack(anchor="w", padx=20, pady=(10, 0))  # section heading

calendar_button = tk.Button(  # create the button that opens the Ikalendar availability calendar
    form_frame,
    text="Please Check our Calendar for Availability date and time",  # the exact button label requested
    wraplength=300,  # wrap the text onto multiple lines so the button isn't too wide
    bg="#2196F3", fg="white",  # blue background, white text, to stand out from the Submit button
    command=lambda: ikalendar.open_calendar(window)  # clicking it opens the Ikalendar pop-up, passing our window as its parent
)
calendar_button.pack(padx=20, pady=(10, 5), anchor="w")  # place the button with spacing, left-aligned

FULL_START_TIME_OPTIONS = [f"{hour:02d}:00" for hour in range(9, 22)]  # 09:00, 10:00, ... 21:00
FULL_END_TIME_OPTIONS = [f"{hour:02d}:00" for hour in range(11, 23)]  # 11:00, 12:00, ... 22:00

# --- Event Date: a button that opens the monthly calendar picker, instead of a text box ---
tk.Label(form_frame, text="Event Date *").pack(anchor="w", padx=20)  # the field's label
selected_event_date = {"value": None}  # holds the actually-chosen date object (starts empty, nothing picked yet)
event_date_button = tk.Button(form_frame, text="Click to choose a date")  # shows the chosen date once picked (command set below)
event_date_button.pack(padx=20, pady=(0, 8), anchor="w")  # place the button

# --- Start Time / End Time: dropdown menus, instead of text boxes ---
tk.Label(form_frame, text="Start Time *").pack(anchor="w", padx=20)  # label for the start time dropdown
start_time_var = tk.StringVar(window)  # holds the currently selected start time
start_time_dropdown = tk.OptionMenu(form_frame, start_time_var, *FULL_START_TIME_OPTIONS)  # the dropdown itself
start_time_dropdown.pack(padx=20, pady=(0, 8), anchor="w")  # place it

tk.Label(form_frame, text="End Time *").pack(anchor="w", padx=20)  # label for the end time dropdown
end_time_var = tk.StringVar(window)  # holds the currently selected end time
end_time_dropdown = tk.OptionMenu(form_frame, end_time_var, *FULL_END_TIME_OPTIONS)  # the dropdown itself
end_time_dropdown.pack(padx=20, pady=(0, 8), anchor="w")  # place it


def refresh_time_options(event_date_obj):
    # this function narrows the Start/End time dropdowns down to only the hours actually
    # open on the chosen date (e.g. Friday closes earlier, so fewer hours should be offered)
    connection = sqlite3.connect("land_farmer.db")  # open a connection
    cursor = connection.cursor()  # create a cursor
    open_time, close_time = get_opening_hours_for_date(cursor, event_date_obj)  # look up this day's hours
    connection.close()  # close the connection

    if open_time is None:  # if the restaurant happens to be closed on this date (shouldn't occur, since the picker already hides closed days)
        valid_start_times = []  # no valid times at all
        valid_end_times = []
    else:  # otherwise, work out which of our fixed options actually fit within this day's hours
        close_time_obj = datetime.datetime.strptime(close_time, "%H:%M")  # parse close_time so we can do time math
        latest_allowed = (close_time_obj - datetime.timedelta(hours=1)).strftime("%H:%M")  # the latest allowed time, 1 hour before closing
        valid_start_times = [t for t in FULL_START_TIME_OPTIONS if open_time < t <= latest_allowed]  # keep only times that fit
        valid_end_times = [t for t in FULL_END_TIME_OPTIONS if open_time < t <= latest_allowed]  # same rule for end times

    # rebuild the Start Time dropdown's menu with just the valid options
    start_menu = start_time_dropdown["menu"]  # get the actual dropdown list part of the widget
    start_menu.delete(0, "end")  # clear out every existing option
    for option in valid_start_times:  # loop through the newly filtered options
        start_menu.add_command(label=option, command=lambda value=option: start_time_var.set(value))  # add each one back in
    start_time_var.set(valid_start_times[0] if valid_start_times else "")  # select the first valid option automatically

    # rebuild the End Time dropdown's menu the same way
    end_menu = end_time_dropdown["menu"]  # get the actual dropdown list part of the widget
    end_menu.delete(0, "end")  # clear out every existing option
    for option in valid_end_times:  # loop through the newly filtered options
        end_menu.add_command(label=option, command=lambda value=option: end_time_var.set(value))  # add each one back in
    end_time_var.set(valid_end_times[-1] if valid_end_times else "")  # select the last valid option automatically (a sensible default end time)


def on_date_picked(chosen_date):
    selected_event_date["value"] = chosen_date  # remember the actual date object
    event_date_button.config(text=chosen_date.strftime("%d/%m/%Y"))  # show the chosen date on the button itself
    refresh_time_options(chosen_date)  # narrow down the time dropdowns to match this date's opening hours


def open_date_picker_clicked():
    earliest = datetime.date.today() + datetime.timedelta(days=1)  # the earliest choosable date is tomorrow (must be after today)
    date_picker.open_date_picker(window, on_date_picked, earliest)  # open the calendar pop-up


event_date_button.config(command=open_date_picker_clicked)  # connect the button to open the calendar

connection = sqlite3.connect("land_farmer.db")  # open a connection, just to read the restaurant's capacity for the label below
cursor = connection.cursor()  # create a cursor
cursor.execute("SELECT total_capacity FROM Settings LIMIT 1")  # get the restaurant's total capacity
RESTAURANT_CAPACITY = cursor.fetchone()[0]  # extract the number
connection.close()  # close the connection

num_guests_entry = add_field(f"Number of Guests (max {RESTAURANT_CAPACITY})", True)  # required field for guest count, showing the capacity
event_type_entry = add_field("Event Type (e.g. Birthday, Wedding)", False)  # optional field for event type
dietary_entry = add_field("Dietary Restrictions / Allergies", False)  # optional field for dietary info
special_requests_entry = add_field("Special Requests", False)  # optional field for special requests
notes_entry = add_field("Notes", False)  # optional field for general notes

status_label = tk.Label(form_frame, text="", fg="red", wraplength=440)  # a label to show error/warning messages, red text
status_label.pack(pady=10)  # place it below the form fields


# ---------------------------------------------------------------------------
# BUTTON ACTIONS
# ---------------------------------------------------------------------------

def clear_form():
    # this function empties every entry box, so the form is ready for the next request
    for entry in [first_name_entry, last_name_entry, id_number_entry, company_name_entry,
                  company_id_entry, phone_entry, email_entry, num_guests_entry, event_type_entry,
                  dietary_entry, special_requests_entry, notes_entry]:  # loop through every text entry box
        entry.delete(0, tk.END)  # delete() removes text from position 0 to the end, clearing the box
    selected_event_date["value"] = None  # forget the previously chosen date
    event_date_button.config(text="Click to choose a date")  # reset the date button's display text
    start_time_var.set("")  # clear the chosen start time
    end_time_var.set("")  # clear the chosen end time


def build_menu_clicked():
    # this function runs when "Build Your Menu" is clicked - it validates and saves the request,
    # then opens the menu-building screen for the client to choose their meal and get a quote
    # read every field's current text, and strip() removes accidental extra spaces at the start/end
    first_name = first_name_entry.get().strip()
    last_name = last_name_entry.get().strip()
    id_number = id_number_entry.get().strip()
    company_name = company_name_entry.get().strip()
    company_id_number = company_id_entry.get().strip()
    phone = phone_entry.get().strip()
    email = email_entry.get().strip()
    event_date_obj = selected_event_date["value"]  # this is a real date object, or None if nothing was picked yet
    start_time = start_time_var.get()  # read the chosen start time from the dropdown
    end_time = end_time_var.get()  # read the chosen end time from the dropdown
    num_guests_text = num_guests_entry.get().strip()
    event_type = event_type_entry.get().strip()
    dietary_restrictions = dietary_entry.get().strip()
    special_requests = special_requests_entry.get().strip()
    notes = notes_entry.get().strip()

    # check that every REQUIRED field has something filled in (event_type is optional, per the rules)
    if event_date_obj is None:  # a date must have been picked from the calendar
        status_label.config(text="Please choose an Event Date from the calendar.")  # show an error message
        return  # stop here
    required_values = [first_name, last_name, id_number, phone, email, start_time, end_time, num_guests_text]  # list of required text values
    if "" in required_values:  # if any required value is still an empty string
        status_label.config(text="Please fill in all required fields (marked with *).")  # show an error message
        return  # stop here - don't try to save anything yet

    # length/format checks for the Customer fields
    if len(first_name) > 20:  # first name has a maximum length of 20 characters
        status_label.config(text="First Name must be 20 characters or fewer.")
        return
    if len(last_name) > 20:  # last name has a maximum length of 20 characters
        status_label.config(text="Last Name must be 20 characters or fewer.")
        return
    if not id_number.isdigit() or len(id_number) > 10:  # isdigit() checks every character is 0-9
        status_label.config(text="ID Number must contain only digits, up to 10 digits.")
        return
    if company_name != "" and len(company_name) > 20:  # only check length if something was actually typed
        status_label.config(text="Company Name must be 20 characters or fewer.")
        return
    if company_id_number != "" and (not company_id_number.isdigit() or len(company_id_number) > 10):  # same idea for company ID
        status_label.config(text="Company ID Number must contain only digits, up to 10 digits.")
        return
    if len(phone) > 10:  # phone has a maximum length of 10 characters
        status_label.config(text="Phone must be 10 characters or fewer.")
        return
    if len(email) > 50 or "@" not in email:  # email must be short enough AND contain an @ symbol
        status_label.config(text="Email must be 50 characters or fewer, and contain '@'.")
        return

    # length checks for the Event fields
    if event_type != "" and len(event_type) > 20:  # event type is optional, but limited to 20 characters if given
        status_label.config(text="Event Type must be 20 characters or fewer.")
        return
    if len(dietary_restrictions) > 100:  # dietary restrictions has a maximum length of 100 characters
        status_label.config(text="Dietary Restrictions must be 100 characters or fewer.")
        return
    if len(special_requests) > 200:  # special requests has a maximum length of 200 characters
        status_label.config(text="Special Requests must be 200 characters or fewer.")
        return
    if len(notes) > 200:  # notes has a maximum length of 200 characters
        status_label.config(text="Notes must be 200 characters or fewer.")
        return

    # check that num_guests is actually a valid positive whole number
    try:
        num_guests = int(num_guests_text)  # try converting the typed text into a whole number
    except ValueError:  # this happens if the text isn't a valid number, e.g. "abc"
        status_label.config(text="Number of Guests must be a whole number.")  # show an error message
        return  # stop here

    if num_guests <= 0:  # guest count must be positive
        status_label.config(text="Number of Guests must be greater than 0.")  # show an error message
        return  # stop here

    # the event date came from the calendar picker, so it's already a real, valid date object -
    # just convert it to "YYYY-MM-DD" text, which is what we store in the database
    event_date = event_date_obj.isoformat()

    if start_time >= end_time:  # since times are zero-padded HH:MM text, we can compare them directly
        status_label.config(text="Start Time must be earlier than End Time.")  # show an error message
        return  # stop here

    today = datetime.date.today()  # get today's real date

    # the event date must be at least one day after today (since request_date is always today)
    if event_date_obj <= today:  # compare the two date objects directly
        status_label.config(text="Event Date must be at least one day after today.")  # show an error message
        return  # stop here

    # now connect to the database to check opening hours, capacity, and overlapping bookings
    connection = sqlite3.connect("land_farmer.db")  # open a connection to the database
    cursor = connection.cursor()  # create a cursor to run commands with

    open_time, close_time = get_opening_hours_for_date(cursor, event_date_obj)  # look up this day's opening hours
    if open_time is None:  # if the restaurant is closed on this day
        status_label.config(text="The restaurant is closed on this day. Please choose a different date.")
        connection.close()
        return  # stop here

    # the latest allowed time is one hour before closing
    close_time_obj = datetime.datetime.strptime(close_time, "%H:%M")  # parse close_time so we can do time math on it
    latest_allowed = (close_time_obj - datetime.timedelta(hours=1)).strftime("%H:%M")  # subtract 1 hour, format back to text

    if not (open_time < start_time <= latest_allowed):  # start_time must be after opening, and at or before the latest allowed time
        status_label.config(text=f"Start Time must be after {open_time} and by {latest_allowed} at the latest.")
        connection.close()
        return  # stop here

    if not (open_time < end_time <= latest_allowed):  # end_time must follow the exact same rule
        status_label.config(text=f"End Time must be after {open_time} and by {latest_allowed} at the latest.")
        connection.close()
        return  # stop here

    cursor.execute("SELECT total_capacity FROM Settings LIMIT 1")  # get the restaurant's total capacity
    total_capacity = cursor.fetchone()[0]  # extract the number
    if num_guests > total_capacity:  # number of guests can never exceed the restaurant's total capacity
        status_label.config(text=f"Number of Guests cannot exceed the restaurant's capacity of {total_capacity}.")
        connection.close()
        return  # stop here

    already_booked, total_capacity, total_after = check_capacity(cursor, event_date, start_time, end_time, num_guests)  # run our overlap/capacity check

    if total_after > total_capacity:  # if saving this request would exceed the restaurant's capacity for that time slot
        proceed = messagebox.askyesno(  # show a Yes/No pop-up box asking if we should still continue
            "Capacity Warning",
            f"Already booked in this time range: {already_booked} guests.\n"
            f"Restaurant capacity: {total_capacity} guests.\n"
            f"Adding this request ({num_guests} guests) would bring the total to {total_after}.\n\n"
            "Do you still want to save this request?"
        )
        if not proceed:  # if the admin clicked "No"
            connection.close()  # close the database connection since we're not saving
            status_label.config(text="Request not saved.")  # tell the user nothing was saved
            return  # stop here

    # convert any empty OPTIONAL fields to None, so they're stored as proper empty (NULL) values rather than blank text
    company_name_value = company_name if company_name != "" else None  # None if left blank
    company_id_value = company_id_number if company_id_number != "" else None  # None if left blank
    event_type_value = event_type if event_type != "" else None  # None if left blank
    dietary_value = dietary_restrictions if dietary_restrictions != "" else None  # None if left blank
    special_requests_value = special_requests if special_requests != "" else None  # None if left blank
    notes_value = notes if notes != "" else None  # None if left blank

    # find the matching customer, or create a new one, then save the request
    try:
        customer_id = find_or_create_customer(cursor, first_name, last_name, id_number,
                                               company_name_value, company_id_value, phone, email)  # get or create the customer
        connection.commit()  # save the customer insert (if any) before we move on
        connection.close()  # close this connection since save_request() opens its own
        new_request_number = save_request(customer_id, event_date, start_time, end_time, num_guests, event_type_value,
                                           dietary_value, special_requests_value, notes_value)  # save the request, get its new number back
        status_label.config(fg="green", text=f"Request #{new_request_number} saved! Opening menu builder...")  # show a success message in green
        build_your_menu.open_menu_builder(window, new_request_number, on_complete=window.destroy)  # open the menu builder; once they confirm, close this whole window - nothing should reappear
    except sqlite3.IntegrityError as error:  # this catches database rule violations, e.g. duplicate id_number issues
        status_label.config(fg="red", text=f"Could not save: {error}")  # show the database's error message


menu_button = tk.Button(form_frame, text="Build Your Menu", command=build_menu_clicked, bg="#4CAF50", fg="white")  # the main action button
menu_button.pack(pady=5, before=status_label)  # place it right after the Notes field, before the status message

clear_button = tk.Button(form_frame, text="Clear Form", command=clear_form)  # a button to manually clear the form
clear_button.pack(pady=10)  # place the clear button with some spacing, extra space at the bottom so it's not flush with the edge

window.mainloop()  # start the GUI event loop - this keeps the window open and responsive until closed
