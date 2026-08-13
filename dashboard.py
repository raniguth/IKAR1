# dashboard.py
# PURPOSE OF THIS FILE:
# This file is the main "home screen" of the Land Farmer app for Dikla, the
# manager. It shows a weekly summary table (last/this/next week), 6 buttons
# that open other screens (calendar, today's events, all events, customers,
# payment updates, and feedback entry), and a bar chart of the last 10 days'
# income.

import tkinter as tk  # import the GUI library, nicknamed "tk"
from tkinter import messagebox  # import the pop-up message box part of tkinter
import sqlite3  # import the library that lets Python talk to the SQLite database
import datetime  # import the library that helps us work with dates and times
import os  # import the library that lets us interact with the operating system (used here to trigger printing)
import tempfile  # import the library that creates temporary files (used here to build the file we send to the printer)
import subprocess  # import the library that lets us launch another Python file as its own separate program
import sys  # import the library that tells us which Python program is currently running us
import ikalendar  # import our Ikalendar module, so the IKALENDAR button can open it

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

# matplotlib draws the income chart - it embeds directly inside our tkinter window
import matplotlib  # import the main plotting library
matplotlib.use("TkAgg")  # tell matplotlib to draw using tkinter's drawing surface
import matplotlib.pyplot as plt  # the part of matplotlib used to build a chart
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # lets us place a matplotlib chart inside a tkinter window

MANAGER_NAME = "DIKLA"  # the name shown in the welcome message at the top


def get_connection():
    return sqlite3.connect("land_farmer.db")  # open (and return) a fresh connection to our database file


# ---------------------------------------------------------------------------
# DATABASE / LOGIC HELPER FUNCTIONS
# ---------------------------------------------------------------------------

def get_week_start(reference_date):
    # returns the Sunday date of the week containing reference_date (same logic as Ikalendar)
    days_since_sunday = (reference_date.weekday() + 1) % 7  # weekday(): Monday=0..Sunday=6, this converts to "days since Sunday"
    return reference_date - datetime.timedelta(days=days_since_sunday)  # subtract that many days to land on Sunday


def get_week_summary(cursor, week_start, week_end):
    # returns (event_count, total_guests, total_income) for every Event between week_start and week_end
    cursor.execute("""
        SELECT COUNT(*), COALESCE(SUM(num_guests), 0), COALESCE(SUM(total_price), 0)
        FROM Events WHERE event_date BETWEEN ? AND ?
    """, (week_start.isoformat(), week_end.isoformat()))  # COALESCE turns "no rows" into 0 instead of None
    return cursor.fetchone()  # return the single row of results: (count, guests, income)


def get_last_10_days_income(cursor, today):
    # returns a list of (date, income) pairs for each of the last 10 days (including today),
    # where income is the sum of deposit_paid for events on that date
    results = []  # start with an empty list to build up
    for days_ago in range(9, -1, -1):  # count down from 9 to 0, so the oldest day comes first
        day = today - datetime.timedelta(days=days_ago)  # calculate this day's actual date
        cursor.execute("SELECT COALESCE(SUM(deposit_paid), 0) FROM Events WHERE event_date = ?", (day.isoformat(),))  # sum that day's deposits
        income = cursor.fetchone()[0]  # extract the number
        results.append((day, income))  # add this day's (date, income) pair to our list
    return results  # give back all 10 pairs


def copy_to_clipboard(value):
    # copies any value onto the computer's clipboard, so it can be pasted elsewhere
    window.clipboard_clear()  # empty whatever was previously on the clipboard
    window.clipboard_append(str(value))  # place our value onto the clipboard
    window.update()  # this keeps the copied value available even after our window loses focus


def next_product_id(cursor):
    # looks at every existing product_id (like "M1", "M23"...) and returns the next unused one
    cursor.execute("SELECT product_id FROM MenuProducts")  # get every existing product_id
    highest_number_so_far = 0  # start assuming we haven't seen any numbered IDs yet
    for (product_id,) in cursor.fetchall():  # loop through each one (each row is a 1-item tuple, hence the comma)
        if product_id.startswith("M") and product_id[1:].isdigit():  # only look at IDs matching our "M<number>" pattern
            number = int(product_id[1:])  # pull out just the number part and convert it
            if number > highest_number_so_far:  # keep track of the largest number we've seen
                highest_number_so_far = number
    return f"M{highest_number_so_far + 1}"  # the next free ID is one higher than the largest we found


def cancel_event(event_id):
    # this function cancels an Event: marks its original Request as Declined, and removes the Event itself
    connection = get_connection()  # open a connection
    cursor = connection.cursor()  # create a cursor
    cursor.execute("SELECT request_number FROM Events WHERE event_id = ?", (event_id,))  # find which Request this event came from
    request_number = cursor.fetchone()[0]  # extract the request_number
    cursor.execute("UPDATE Requests SET status = 'Declined' WHERE request_number = ?", (request_number,))  # mark the original request Declined
    cursor.execute("DELETE FROM EventProducts WHERE event_id = ?", (event_id,))  # remove this event's chosen products first
    cursor.execute("DELETE FROM Events WHERE event_id = ?", (event_id,))  # then remove the event itself
    connection.commit()  # save all these changes permanently
    connection.close()  # close the connection


# ---------------------------------------------------------------------------
# GUI SETUP: MAIN DASHBOARD WINDOW
# ---------------------------------------------------------------------------

window = tk.Tk()  # create the main application window
window.title("Land Farmer - Dashboard")  # set the window's title bar text
window.geometry("800x850")  # set the starting window size

canvas = tk.Canvas(window)  # a scrollable drawing surface, in case content is taller than the window
scrollbar = tk.Scrollbar(window, orient="vertical", command=canvas.yview)  # a vertical scrollbar linked to the canvas
main_frame = tk.Frame(canvas)  # a frame to hold everything else in this window
main_frame.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))  # keep the scroll area updated
canvas.create_window((0, 0), window=main_frame, anchor="nw")  # place main_frame inside the canvas
canvas.configure(yscrollcommand=scrollbar.set)  # connect the canvas's vertical position to the scrollbar
canvas.pack(side="left", fill="both", expand=True)  # place the canvas, filling remaining space
scrollbar.pack(side="right", fill="y")  # place the scrollbar along the right edge


def on_mousewheel(event):
    canvas.yview_scroll(-1 * (event.delta // 120), "units")  # scroll the canvas up/down with the mouse wheel


canvas.bind_all("<MouseWheel>", on_mousewheel)  # activate mouse wheel scrolling over the window

tk.Label(main_frame, text=f"HELLO {MANAGER_NAME}", font=("Arial", 20, "bold")).pack(pady=20)  # the welcome message

# ---------------------------------------------------------------------------
# WEEKLY SUMMARY TABLE
# ---------------------------------------------------------------------------

table_frame = tk.Frame(main_frame)  # a frame to hold the weekly summary table
table_frame.pack(pady=10)  # place it below the welcome message


def build_weekly_table():
    # this function draws (or redraws) the weekly summary table from scratch, using the latest data
    for widget in table_frame.winfo_children():  # loop through every widget currently in the table frame
        widget.destroy()  # remove it, so we can draw the table fresh

    headers = ["Week", "Dates", "Events", "Guests", "Income (₪)"]  # the table's column titles
    for col, header_text in enumerate(headers):  # loop through each header, keeping track of its column number
        tk.Label(table_frame, text=header_text, font=("Arial", 10, "bold"), relief="solid", width=14, padx=5, pady=5).grid(row=0, column=col)  # header cell

    connection = get_connection()  # open a connection
    cursor = connection.cursor()  # create a cursor
    today = datetime.date.today()  # get today's real date
    this_week_start = get_week_start(today)  # find the Sunday of the current week

    week_rows = [  # each tuple is (display label, that week's Sunday)
        ("Last Week", this_week_start - datetime.timedelta(days=7)),
        ("This Week", this_week_start),
        ("Next Week", this_week_start + datetime.timedelta(days=7)),
    ]

    for row_number, (label, week_start) in enumerate(week_rows, start=1):  # loop through all 3 weeks, row 1 is the first data row
        week_end = week_start + datetime.timedelta(days=6)  # the Saturday that ends this week
        event_count, total_guests, total_income = get_week_summary(cursor, week_start, week_end)  # get this week's numbers
        date_range_text = f"{week_start.strftime('%d/%m')} - {week_end.strftime('%d/%m')}"  # build the "DD/MM - DD/MM" text

        row_values = [label, date_range_text, str(event_count), str(total_guests), f"{total_income:,.2f}"]  # every cell's text for this row
        for col, value in enumerate(row_values):  # loop through each value, keeping track of its column number
            tk.Label(table_frame, text=value, relief="solid", width=14, padx=5, pady=5).grid(row=row_number, column=col)  # data cell

    connection.close()  # close the connection, we've loaded everything the table needs


build_weekly_table()  # draw the table for the first time when the dashboard opens

# ---------------------------------------------------------------------------
# CREATE A LINK TO A NEW EVENT REQUEST
# Generates a unique, single-use token for one potential client. For now
# (while this app runs only on your own computer, not a real website), the
# "link" shown here is a placeholder - the real, clickable version will only
# work once the app is deployed as a website. To test the one-link-one-client
# behavior locally today, use the companion file open_request_by_link.py
# with the token that gets shown/copied.
# ---------------------------------------------------------------------------

import secrets  # import the library used to generate a secure, hard-to-guess random token


def create_request_link_clicked():
    token = secrets.token_urlsafe(16)  # generate a long, random, practically-impossible-to-guess piece of text
    created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # capture exactly when this link was created

    connection = get_connection()  # open a connection
    cursor = connection.cursor()  # create a cursor
    cursor.execute("INSERT INTO RequestLinks (link_token, created_at) VALUES (?, ?)", (token, created_at))  # save the new, unused link
    connection.commit()  # save it permanently
    connection.close()  # close the connection

    placeholder_link = f"http://localhost:8000/new-request/{token}"  # this exact address will only work once the app is a real website
    copy_to_clipboard(placeholder_link)  # copy it to the clipboard, ready to paste into an email/WhatsApp/etc.

    messagebox.showinfo(
        "Link Created",
        f"A new, one-time link has been created and copied to your clipboard:\n\n{placeholder_link}\n\n"
        "IMPORTANT: this exact web address will only work once the app is deployed online. "
        "For local testing right now, give the client this token instead:\n\n"
        f"{token}\n\n"
        "and have them run open_request_by_link.py with it - that will open a fresh "
        "New Event Request form for them, and this exact token can never be reused afterward."
    )  # explain clearly what will and won't work yet


create_link_button = tk.Button(
    main_frame,
    text="Create a Link to a New Event Request",
    command=create_request_link_clicked,
    font=("Arial", 11, "bold"), bg="#4CAF50", fg="white", width=32, height=2
)  # the new button, placed above the icon grid
create_link_button.pack(pady=(5, 15))  # place it between the weekly table and the icon buttons

# ---------------------------------------------------------------------------
# NAVIGATION BUTTONS
# ---------------------------------------------------------------------------

buttons_frame = tk.Frame(main_frame)  # a frame to hold the 6 navigation buttons
buttons_frame.pack(pady=25)  # place it below the summary table

BUTTON_STYLE = {"font": ("Arial", 11, "bold"), "width": 14, "height": 2, "bg": "#2196F3", "fg": "white"}  # shared button appearance


open_ikalendar_redraw = {"function": None}  # remembers the currently-open Ikalendar's own redraw function, if any is open


def open_ikalendar_clicked():
    # open_calendar() hands back its own draw_week function - we hold onto it so REFRESH can use it later
    open_ikalendar_redraw["function"] = ikalendar.open_calendar(window, allow_past_weeks=True)  # open the FULL admin calendar (past weeks allowed)


tk.Button(buttons_frame, text="IKALENDAR", command=open_ikalendar_clicked, **BUTTON_STYLE).grid(row=0, column=0, padx=10, pady=10)  # button 1
tk.Button(buttons_frame, text="TODAY", command=lambda: open_today_window(), **BUTTON_STYLE).grid(row=0, column=1, padx=10, pady=10)  # button 2
tk.Button(buttons_frame, text="EVENTS", command=lambda: open_events_window(), **BUTTON_STYLE).grid(row=0, column=2, padx=10, pady=10)  # button 3
tk.Button(buttons_frame, text="CUSTOMERS", command=lambda: open_customers_window(), **BUTTON_STYLE).grid(row=1, column=0, padx=10, pady=10)  # button 4
tk.Button(buttons_frame, text="UPDATE", command=lambda: open_update_window(), **BUTTON_STYLE).grid(row=1, column=1, padx=10, pady=10)  # button 5
tk.Button(buttons_frame, text="FEEDBACK", command=lambda: open_feedback_window(), **BUTTON_STYLE).grid(row=1, column=2, padx=10, pady=10)  # button 6


def refresh_dashboard_clicked():
    build_weekly_table()  # redraw the weekly summary table with the latest numbers
    build_income_chart()  # redraw the income chart with the latest numbers
    if open_ikalendar_redraw["function"] is not None:  # if an Ikalendar window has been opened at some point
        try:
            open_ikalendar_redraw["function"]()  # try redrawing it with the latest data
        except tk.TclError:  # this happens if that calendar window has since been closed
            open_ikalendar_redraw["function"] = None  # forget it, so we don't try again next time


REFRESH_STYLE = {"font": ("Arial", 11, "bold"), "width": 14, "height": 2, "bg": "#9C27B0", "fg": "white"}  # a distinct color for these 3 extra buttons
tk.Button(buttons_frame, text="REFRESH", command=refresh_dashboard_clicked, **REFRESH_STYLE).grid(row=2, column=0, padx=10, pady=10)  # button 7
tk.Button(buttons_frame, text="MENU", command=lambda: open_menu_products_window(), **REFRESH_STYLE).grid(row=2, column=1, padx=10, pady=10)  # button 8
tk.Button(buttons_frame, text="EXTRAS", command=lambda: open_extras_window(), **REFRESH_STYLE).grid(row=2, column=2, padx=10, pady=10)  # button 9

# ---------------------------------------------------------------------------
# TODAY WINDOW
# ---------------------------------------------------------------------------

def open_today_window():
    today_window = tk.Toplevel(window)  # a new pop-up window
    today_window.title("Today's Events")  # set its title bar text
    today_window.geometry("850x420")  # set its size

    today_date = datetime.date.today()  # get today's real date
    tk.Label(today_window, text=f"{today_date.strftime('%A')}, {today_date.strftime('%d/%m/%Y')}",
             font=("Arial", 14, "bold")).pack(pady=10)  # heading: day name + date

    canvas7 = tk.Canvas(today_window)  # a scrollable drawing surface, in case there are many events today
    scrollbar7 = tk.Scrollbar(today_window, orient="vertical", command=canvas7.yview)  # its vertical scrollbar
    rows_frame = tk.Frame(canvas7)  # the frame that will actually hold all the event rows
    rows_frame.bind("<Configure>", lambda event: canvas7.configure(scrollregion=canvas7.bbox("all")))  # keep scroll area updated
    canvas7.create_window((0, 0), window=rows_frame, anchor="nw")  # place rows_frame inside the canvas
    canvas7.configure(yscrollcommand=scrollbar7.set)  # connect the canvas's vertical position to the scrollbar
    canvas7.pack(side="left", fill="both", expand=True, padx=10, pady=5)  # place the canvas
    scrollbar7.pack(side="right", fill="y")  # place the scrollbar

    def on_mousewheel_today(event):
        canvas7.yview_scroll(-1 * (event.delta // 120), "units")  # scroll the canvas up/down with the mouse wheel
    canvas7.bind_all("<MouseWheel>", on_mousewheel_today)  # activate mouse wheel scrolling over this window

    headers = ["Event ID", "Start Time", "Guests", "Meal", "Total Price", "First Name", "Last Name", "Phone", ""]  # column titles (last one is for the button)
    for col, header_text in enumerate(headers):  # loop through every header
        tk.Label(rows_frame, text=header_text, font=("Arial", 9, "bold"), relief="solid", width=11).grid(row=0, column=col)  # header cell

    connection = get_connection()  # open a connection
    cursor = connection.cursor()  # create a cursor
    cursor.execute("""
        SELECT Events.event_id, Events.event_start_time, Events.num_guests, Events.meal_option, Events.total_price,
               Customers.first_name, Customers.last_name, Customers.phone
        FROM Events JOIN Customers ON Events.customer_id = Customers.customer_id
        WHERE Events.event_date = ?
        ORDER BY Events.event_start_time
    """, (today_date.isoformat(),))  # find every event happening today
    rows = cursor.fetchall()  # get every matching row
    connection.close()  # close the connection

    if not rows:  # if there are no events today
        tk.Label(rows_frame, text="No events scheduled for today.", font=("Arial", 10, "italic")).grid(row=1, column=0, columnspan=9, pady=10)  # message
    else:  # otherwise, show every event
        for row_number, row in enumerate(rows, start=1):  # loop through every event, row 1 is the first data row
            event_id = row[0]  # the first column of each row is always the event_id
            for col, value in enumerate(row):  # loop through each value in this event's row
                tk.Label(rows_frame, text=value, relief="solid", width=11).grid(row=row_number, column=col)  # data cell
            tk.Button(rows_frame, text="View Menu", command=lambda eid=event_id: show_event_menu_details(eid)).grid(row=row_number, column=8, padx=2, pady=1)  # the new button


def show_event_menu_details(event_id):
    # this function shows one event's guest count, start time, chosen products, and any dietary notes for the chef
    connection = get_connection()  # open a connection
    cursor = connection.cursor()  # create a cursor
    cursor.execute("SELECT num_guests, event_start_time, request_number FROM Events WHERE event_id = ?", (event_id,))  # get this event's basic info
    num_guests, event_start_time, request_number = cursor.fetchone()  # unpack the single matching row
    cursor.execute("""
        SELECT MenuProducts.product_name FROM EventProducts
        JOIN MenuProducts ON EventProducts.product_id = MenuProducts.product_id
        WHERE EventProducts.event_id = ?
        ORDER BY MenuProducts.product_name
    """, (event_id,))  # get every product chosen for this event, alphabetically
    product_names = [row[0] for row in cursor.fetchall()]  # pull just the names out of each row
    cursor.execute("SELECT dietary_restrictions FROM Requests WHERE request_number = ?", (request_number,))  # get the original request's dietary notes
    dietary_restrictions = cursor.fetchone()[0]  # extract the value (may be None if nothing was noted)
    connection.close()  # close the connection

    detail_window = tk.Toplevel(window)  # a new pop-up window for the details
    detail_window.title(f"Event #{event_id} - Menu")  # set its title bar text
    detail_window.geometry("350x480")  # set its starting size (the scrollbar handles any overflow)

    tk.Label(detail_window, text=f"Guests: {num_guests}", font=("Arial", 11, "bold")).pack(anchor="w", padx=15, pady=(15, 2))  # guest count
    tk.Label(detail_window, text=f"Start Time: {event_start_time}", font=("Arial", 11, "bold")).pack(anchor="w", padx=15, pady=(0, 10))  # start time

    # this bottom section is packed FIRST with side="bottom", so it reserves its own fixed space
    # at the bottom of the window, no matter how tall the scrollable product list above it grows
    def print_menu_report():
        # build a plain-text report of everything shown in this window
        report_lines = [f"Event #{event_id} - Menu"]  # start with a title line
        report_lines.append(f"Guests: {num_guests}")  # add the guest count
        report_lines.append(f"Start Time: {event_start_time}")  # add the start time
        report_lines.append("")  # a blank line for spacing
        report_lines.append("Chosen Products:")  # products section heading
        if product_names:  # if any products were chosen
            for name in product_names:  # loop through every chosen product
                report_lines.append(f"- {name}")  # add it as its own line
        else:  # if nothing was chosen
            report_lines.append("(none)")  # note that
        report_lines.append("")  # a blank line for spacing
        report_lines.append("Important notes for the Chef !")  # chef notes heading
        report_lines.append(dietary_restrictions if dietary_restrictions else "(none)")  # the actual notes
        report_text = "\n".join(report_lines)  # join every line together with line breaks between them

        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")  # create a temporary text file
        temp_file.write(report_text)  # write our report into it
        temp_file.close()  # close it so other programs (like the printer) can safely open it

        try:
            os.startfile(temp_file.name, "print")  # ask Windows to send this file to your default printer
            messagebox.showinfo("Print", "Sent to the printer.")  # confirm success
        except Exception as error:  # this catches any printing failure (e.g. no printer set up, or not running on Windows)
            messagebox.showerror("Print Failed", f"Could not print: {error}")  # show what went wrong

    print_frame = tk.Frame(detail_window)  # a frame to hold the print button
    print_frame.pack(side="bottom", pady=(0, 10))  # place it at the very bottom of the window
    tk.Button(print_frame, text="PRINT", command=print_menu_report, bg="#2196F3", fg="white",
              font=("Arial", 10, "bold")).pack()  # the print button

    chef_notes_frame = tk.Frame(detail_window)  # a frame to hold the chef notes section
    chef_notes_frame.pack(side="bottom", fill="x", padx=15, pady=15)  # place it, pinned to the bottom (just above the print button)
    tk.Label(chef_notes_frame, text="Important notes for the Chef !", font=("Arial", 10, "bold"), fg="#B71C1C").pack(anchor="w", pady=(10, 2))  # heading
    tk.Label(chef_notes_frame, text=dietary_restrictions if dietary_restrictions else "(none)",
             font=("Arial", 10), wraplength=300, justify="left", anchor="w").pack(anchor="w")  # the actual dietary restrictions text

    tk.Label(detail_window, text="Chosen Products:", font=("Arial", 10, "bold")).pack(anchor="w", padx=15)  # products heading

    canvas8 = tk.Canvas(detail_window)  # a scrollable drawing surface, in case the product list is long
    scrollbar8 = tk.Scrollbar(detail_window, orient="vertical", command=canvas8.yview)  # its vertical scrollbar
    products_frame = tk.Frame(canvas8)  # the frame that will actually hold each product's row
    products_frame.bind("<Configure>", lambda event: canvas8.configure(scrollregion=canvas8.bbox("all")))  # keep scroll area updated
    canvas8.create_window((0, 0), window=products_frame, anchor="nw")  # place products_frame inside the canvas
    canvas8.configure(yscrollcommand=scrollbar8.set)  # connect the canvas's vertical position to the scrollbar
    canvas8.pack(side="left", fill="both", expand=True, padx=(15, 0), pady=(5, 15))  # place the canvas, filling whatever space remains
    scrollbar8.pack(side="right", fill="y", pady=(5, 15))  # place the scrollbar

    def on_mousewheel_detail(event):
        canvas8.yview_scroll(-1 * (event.delta // 120), "units")  # scroll the canvas up/down with the mouse wheel
    canvas8.bind_all("<MouseWheel>", on_mousewheel_detail)  # activate mouse wheel scrolling over this window

    if not product_names:  # if no products were chosen for this event
        tk.Label(products_frame, text="(none)", font=("Arial", 9, "italic")).pack(anchor="w")  # show a placeholder message
    else:  # otherwise, show every product on its own row
        for name in product_names:  # loop through every chosen product name
            tk.Label(products_frame, text=f"• {name}", anchor="w").pack(anchor="w", fill="x")  # one row per product


# ---------------------------------------------------------------------------
# EVENTS WINDOW (future events, clickable rows)

# ---------------------------------------------------------------------------

def open_events_window():
    events_window = tk.Toplevel(window)  # a new pop-up window
    events_window.title("Upcoming Events")  # set its title bar text
    events_window.geometry("700x480")  # set its size

    tk.Label(events_window, text="Upcoming Events (oldest to newest) - click a row for details",
             font=("Arial", 12, "bold")).pack(pady=10)  # heading

    canvas3 = tk.Canvas(events_window)  # a scrollable drawing surface, since there may be many events
    scrollbar3 = tk.Scrollbar(events_window, orient="vertical", command=canvas3.yview)  # its vertical scrollbar
    rows_frame = tk.Frame(canvas3)  # the frame that will actually hold all the event rows
    rows_frame.bind("<Configure>", lambda event: canvas3.configure(scrollregion=canvas3.bbox("all")))  # keep scroll area updated
    canvas3.create_window((0, 0), window=rows_frame, anchor="nw")  # place rows_frame inside the canvas
    canvas3.configure(yscrollcommand=scrollbar3.set)  # connect the canvas's vertical position to the scrollbar
    canvas3.pack(side="left", fill="both", expand=True, padx=10)  # place the canvas
    scrollbar3.pack(side="right", fill="y")  # place the scrollbar

    def load_and_draw_rows():
        for widget in rows_frame.winfo_children():  # loop through every widget currently shown
            widget.destroy()  # remove it, so we can draw the list fresh

        connection = get_connection()  # open a connection
        cursor = connection.cursor()  # create a cursor
        cursor.execute("""
            SELECT Events.event_id, Events.event_date, Customers.first_name, Customers.last_name, Customers.phone
            FROM Events JOIN Customers ON Events.customer_id = Customers.customer_id
            WHERE Events.event_date >= ?
            ORDER BY Events.event_date ASC
        """, (datetime.date.today().isoformat(),))  # find every future event, oldest (soonest) first
        rows = cursor.fetchall()  # get every matching row
        connection.close()  # close the connection

        if not rows:  # if there are no upcoming events at all
            tk.Label(rows_frame, text="No upcoming events.", font=("Arial", 10, "italic")).pack(pady=10)  # show a message
            return  # nothing more to draw

        for event_id, event_date, first_name, last_name, phone in rows:  # loop through every event
            row_frame = tk.Frame(rows_frame, relief="solid", borderwidth=1)  # a bordered box for this one event's row
            row_frame.pack(fill="x", padx=5, pady=3)  # place it, stretching to the full width

            info_text = f"#{event_id} | {event_date} | {first_name} {last_name} | {phone}"  # the readable summary
            info_label = tk.Label(row_frame, text=info_text, anchor="w", cursor="hand2")  # clicking this text opens the details
            info_label.pack(side="left", padx=5, fill="x", expand=True)  # place it
            info_label.bind("<Button-1>", lambda event, eid=event_id: show_event_details(eid))  # open details when clicked

            tk.Button(row_frame, text="📋 Copy Phone", command=lambda p=phone: copy_to_clipboard(p)).pack(side="left", padx=3)  # copy-phone button

            def make_cancel_handler(eid=event_id):
                # this builds a ready-to-use function for ONE specific row's Cancel button
                def cancel_clicked():
                    confirmed = messagebox.askyesno("Confirm Cancellation", f"Are you sure you want to cancel Event #{eid}?")  # ask for confirmation
                    if confirmed:  # only proceed if the admin clicked "Yes"
                        cancel_event(eid)  # mark the request Declined and remove the event
                        load_and_draw_rows()  # redraw the list so the cancelled event disappears
                return cancel_clicked  # give back this ready-to-use function

            tk.Button(row_frame, text="❌ Cancel", fg="white", bg="#F44336", command=make_cancel_handler()).pack(side="left", padx=3)  # cancel button

    load_and_draw_rows()  # draw the list for the first time when the window opens


def show_event_details(event_id):
    connection = get_connection()  # open a connection
    cursor = connection.cursor()  # create a cursor
    cursor.execute("""
        SELECT Events.event_id, Customers.first_name, Customers.last_name, Customers.phone,
               Events.event_start_time, Events.num_guests, Events.meal_option, Events.total_price,
               Events.event_type, Events.dietary_restrictions, Events.special_requests, Events.notes
        FROM Events JOIN Customers ON Events.customer_id = Customers.customer_id
        WHERE Events.event_id = ?
    """, (event_id,))  # find this specific event's details
    details = cursor.fetchone()  # get the single matching row
    connection.close()  # close the connection

    detail_window = tk.Toplevel(window)  # a new pop-up window for the details
    detail_window.title(f"Event #{event_id}")  # set its title bar text
    detail_window.geometry("350x450")  # set its starting size (the scrollbar handles any overflow)

    canvas9 = tk.Canvas(detail_window)  # a scrollable drawing surface, since this window now has quite a few fields
    scrollbar9 = tk.Scrollbar(detail_window, orient="vertical", command=canvas9.yview)  # its vertical scrollbar
    fields_frame = tk.Frame(canvas9)  # the frame that will actually hold every field
    fields_frame.bind("<Configure>", lambda event: canvas9.configure(scrollregion=canvas9.bbox("all")))  # keep scroll area updated
    canvas9.create_window((0, 0), window=fields_frame, anchor="nw")  # place fields_frame inside the canvas
    canvas9.configure(yscrollcommand=scrollbar9.set)  # connect the canvas's vertical position to the scrollbar
    canvas9.pack(side="left", fill="both", expand=True)  # place the canvas, filling remaining space
    scrollbar9.pack(side="right", fill="y")  # place the scrollbar along the right edge

    def on_mousewheel_details(event):
        canvas9.yview_scroll(-1 * (event.delta // 120), "units")  # scroll the canvas up/down with the mouse wheel
    canvas9.bind_all("<MouseWheel>", on_mousewheel_details)  # activate mouse wheel scrolling over this window

    labels = ["Event ID", "First Name", "Last Name", "Phone", "Start Time", "Guests", "Meal Option", "Total Price",
              "Event Type", "Dietary Restrictions", "Special Requests", "Notes"]  # field labels
    for label, value in zip(labels, details):  # pair each label with its matching value
        display_value = value if value is not None else "(none)"  # show "(none)" instead of a blank for empty optional fields
        tk.Label(fields_frame, text=f"{label}: {display_value}", font=("Arial", 10), anchor="w",
                 wraplength=310, justify="left").pack(fill="x", padx=15, pady=4)  # show it, wrapping long text onto multiple lines


# ---------------------------------------------------------------------------
# CUSTOMERS WINDOW (all customers, clickable rows)
# ---------------------------------------------------------------------------

def open_customers_window():
    customers_window = tk.Toplevel(window)  # a new pop-up window
    customers_window.title("All Customers")  # set its title bar text
    customers_window.geometry("600x480")  # set its size

    tk.Label(customers_window, text="All Customers (A-Z) - click a row for details", font=("Arial", 12, "bold")).pack(pady=10)  # heading

    canvas4 = tk.Canvas(customers_window)  # a scrollable drawing surface, since there may be many customers
    scrollbar4 = tk.Scrollbar(customers_window, orient="vertical", command=canvas4.yview)  # its vertical scrollbar
    rows_frame = tk.Frame(canvas4)  # the frame that will actually hold all the customer rows
    rows_frame.bind("<Configure>", lambda event: canvas4.configure(scrollregion=canvas4.bbox("all")))  # keep scroll area updated
    canvas4.create_window((0, 0), window=rows_frame, anchor="nw")  # place rows_frame inside the canvas
    canvas4.configure(yscrollcommand=scrollbar4.set)  # connect the canvas's vertical position to the scrollbar
    canvas4.pack(side="left", fill="both", expand=True, padx=10)  # place the canvas
    scrollbar4.pack(side="right", fill="y")  # place the scrollbar

    connection = get_connection()  # open a connection
    cursor = connection.cursor()  # create a cursor
    cursor.execute("SELECT customer_id, first_name, last_name, phone FROM Customers ORDER BY first_name ASC")  # alphabetical by first name, A-Z
    rows = cursor.fetchall()  # get every matching row
    connection.close()  # close the connection

    for customer_id, first_name, last_name, phone in rows:  # loop through every customer
        row_frame = tk.Frame(rows_frame, relief="solid", borderwidth=1)  # a bordered box for this one customer's row
        row_frame.pack(fill="x", padx=5, pady=3)  # place it, stretching to the full width

        info_text = f"{first_name} {last_name} | {phone}"  # the readable summary
        info_label = tk.Label(row_frame, text=info_text, anchor="w", cursor="hand2")  # clicking this text opens the details
        info_label.pack(side="left", padx=5, fill="x", expand=True)  # place it
        info_label.bind("<Button-1>", lambda event, cid=customer_id: show_customer_details(cid))  # open details when clicked

        tk.Button(row_frame, text="📋 Copy Phone", command=lambda p=phone: copy_to_clipboard(p)).pack(side="left", padx=3)  # copy-phone button


def show_customer_details(customer_id):
    connection = get_connection()  # open a connection
    cursor = connection.cursor()  # create a cursor
    cursor.execute("SELECT first_name, last_name, phone, email, id_number FROM Customers WHERE customer_id = ?", (customer_id,))  # get this customer's info
    first_name, last_name, phone, email, id_number = cursor.fetchone()  # unpack the single matching row

    cursor.execute("""
        SELECT MIN(event_date) FROM Events WHERE customer_id = ? AND event_date >= ?
    """, (customer_id, datetime.date.today().isoformat()))  # find this customer's soonest upcoming event, if any
    upcoming_event_date = cursor.fetchone()[0]  # extract the date (or None if they have no upcoming events)
    connection.close()  # close the connection

    detail_window = tk.Toplevel(window)  # a new pop-up window for the details
    detail_window.title(f"{first_name} {last_name}")  # set its title bar text
    detail_window.geometry("300x250")  # set its size

    fields = [  # every label/value pair to display
        ("First Name", first_name), ("Last Name", last_name), ("Phone", phone),
        ("Email", email), ("ID Number", id_number),
        ("Upcoming Event", upcoming_event_date if upcoming_event_date else "None"),
    ]
    for label, value in fields:  # loop through every field
        tk.Label(detail_window, text=f"{label}: {value}", font=("Arial", 10), anchor="w").pack(fill="x", padx=15, pady=4)  # show it


# ---------------------------------------------------------------------------
# UPDATE WINDOW (last 10 events, with Confirm Payment / Update Price)
# ---------------------------------------------------------------------------

def open_update_window():
    update_window = tk.Toplevel(window)  # a new pop-up window
    update_window.title("Update Payments")  # set its title bar text
    update_window.geometry("700x550")  # set its size

    tk.Label(update_window, text="Last 10 Events", font=("Arial", 12, "bold")).pack(pady=10)  # heading

    canvas2 = tk.Canvas(update_window)  # a scrollable drawing surface, since 10 rows may not all fit
    scrollbar2 = tk.Scrollbar(update_window, orient="vertical", command=canvas2.yview)  # its vertical scrollbar
    rows_frame = tk.Frame(canvas2)  # the frame that will actually hold all the event rows
    rows_frame.bind("<Configure>", lambda event: canvas2.configure(scrollregion=canvas2.bbox("all")))  # keep scroll area updated
    canvas2.create_window((0, 0), window=rows_frame, anchor="nw")  # place rows_frame inside the canvas
    canvas2.configure(yscrollcommand=scrollbar2.set)  # connect the canvas's vertical position to the scrollbar
    canvas2.pack(side="left", fill="both", expand=True, padx=10)  # place the canvas
    scrollbar2.pack(side="right", fill="y")  # place the scrollbar

    connection = get_connection()  # open a connection
    cursor = connection.cursor()  # create a cursor
    cursor.execute("""
        SELECT Events.event_id, Events.meal_option, Events.total_price, Events.deposit_paid,
               Customers.first_name, Customers.last_name, Customers.phone
        FROM Events JOIN Customers ON Events.customer_id = Customers.customer_id
        WHERE Events.event_date <= ?
        ORDER BY Events.event_date DESC, Events.event_id DESC
        LIMIT 10
    """, (datetime.date.today().isoformat(),))  # find the 10 most recent events up to and including today
    rows = list(reversed(cursor.fetchall()))  # reverse() so the oldest of the 10 is shown first, and today's is last
    connection.close()  # close the connection

    def make_confirm_payment_handler(event_id, total_price, confirm_button):
        # this builds a ready-to-use function for ONE specific row's "Confirm Payment" button
        def confirm_payment():
            connection2 = get_connection()  # open a fresh connection for saving
            cursor2 = connection2.cursor()  # create a cursor
            cursor2.execute("UPDATE Events SET deposit_paid = ? WHERE event_id = ?", (total_price, event_id))  # set deposit_paid to the full price
            connection2.commit()  # save the change
            connection2.close()  # close the connection
            confirm_button.config(state="disabled")  # disable this button so it can never be clicked again
        return confirm_payment  # give back this ready-to-use function

    def make_update_price_handler(event_id, confirm_button):
        # this builds a ready-to-use function for ONE specific row's "Update Price" button
        def open_update_price_window():
            price_window = tk.Toplevel(update_window)  # a new pop-up window
            price_window.title("Update Price")  # set its title bar text
            price_window.geometry("250x150")  # set its size
            tk.Label(price_window, text="Update Price", font=("Arial", 12, "bold")).pack(pady=10)  # heading
            price_entry = tk.Entry(price_window, width=15)  # a text box for the new amount
            price_entry.pack(pady=5)  # place it

            def save_new_price():
                price_text = price_entry.get().strip()  # read the typed text
                if not price_text.isdigit():  # isdigit() checks it's a whole number with no minus sign or decimal point
                    messagebox.showerror("Invalid Amount", "Please enter a whole number.")  # show an error
                    return  # stop here
                new_price = int(price_text)  # convert the text into a real integer
                connection3 = get_connection()  # open a fresh connection for saving
                cursor3 = connection3.cursor()  # create a cursor
                cursor3.execute("UPDATE Events SET deposit_paid = ? WHERE event_id = ?", (new_price, event_id))  # save the new amount
                connection3.commit()  # save the change
                connection3.close()  # close the connection
                confirm_button.config(state="disabled")  # a price is now set, so lock the Confirm Payment button too
                price_window.destroy()  # close this small pop-up window

            tk.Button(price_window, text="Update", command=save_new_price, bg="#4CAF50", fg="white").pack(pady=10)  # the Update button
        return open_update_price_window  # give back this ready-to-use function

    for row_number, (event_id, meal_option, total_price, deposit_paid, first_name, last_name, phone) in enumerate(rows):  # loop through every event
        row_frame = tk.Frame(rows_frame, relief="solid", borderwidth=1)  # a bordered box for this one event's row
        row_frame.pack(fill="x", padx=5, pady=4)  # place it, stretching to the full width

        info_text = f"#{event_id} | {meal_option} | ₪{total_price:,.2f} | {first_name} {last_name} | {phone} | Paid: {deposit_paid if deposit_paid is not None else '—'}"  # readable summary
        tk.Label(row_frame, text=info_text, anchor="w").pack(side="left", padx=5, fill="x", expand=True)  # show the summary text

        confirm_button = tk.Button(row_frame, text="Confirm Payment", bg="#4CAF50", fg="white")  # the confirm payment button (command set just below)
        confirm_button.config(command=make_confirm_payment_handler(event_id, total_price, confirm_button))  # wire up its click behavior
        if deposit_paid is not None:  # if a payment amount was already recorded before this window even opened
            confirm_button.config(state="disabled")  # start it disabled, since it's already been "confirmed" once
        confirm_button.pack(side="left", padx=5)  # place the confirm button

        update_price_button = tk.Button(row_frame, text="Update Price", command=make_update_price_handler(event_id, confirm_button))  # the update price button
        update_price_button.pack(side="left", padx=5)  # place the update price button


# ---------------------------------------------------------------------------
# MENU WINDOW (view/edit MenuProducts: name + description)
# ---------------------------------------------------------------------------

def open_menu_products_window():
    menu_window = tk.Toplevel(window)  # a new pop-up window
    menu_window.title("Menu Products")  # set its title bar text
    menu_window.geometry("600x500")  # set its size

    tk.Label(menu_window, text="Menu Products (double-click a row to edit)", font=("Arial", 12, "bold")).pack(pady=10)  # heading

    list_frame = tk.Frame(menu_window)  # a frame to hold the listbox and its scrollbar side by side
    list_frame.pack(fill="both", expand=True, padx=10, pady=5)  # place it, filling remaining space

    scrollbar10 = tk.Scrollbar(list_frame, orient="vertical")  # a vertical scrollbar, attached directly to the listbox below
    scrollbar10.pack(side="right", fill="y")  # place the scrollbar along the right edge

    listbox = tk.Listbox(list_frame, width=75, yscrollcommand=scrollbar10.set)  # the listbox - yscrollcommand keeps the scrollbar in sync as it scrolls
    listbox.pack(side="left", fill="both", expand=True)  # place it, filling the remaining space next to the scrollbar

    scrollbar10.config(command=listbox.yview)  # connect the scrollbar's movement back to actually scrolling the listbox
    # this two-way connection (yscrollcommand + command) is the standard way to pair any tkinter
    # listbox with a real scrollbar - the listbox itself already responds to mouse wheel scrolling too

    connection = get_connection()  # open a connection
    cursor = connection.cursor()  # create a cursor
    cursor.execute("SELECT product_id, product_name, dish_description FROM MenuProducts ORDER BY product_id")  # get every product
    rows = cursor.fetchall()  # get every matching row
    connection.close()  # close the connection

    product_id_map = []  # remembers which product_id belongs to each line in the listbox
    for product_id, product_name, dish_description in rows:  # loop through every product
        line = f"{product_name} - {dish_description or '(no description)'}"  # build a readable line of text
        listbox.insert(tk.END, line)  # add it to the listbox
        product_id_map.append(product_id)  # remember this line's real product_id

    def on_row_double_clicked(clicked_event):
        selection = listbox.curselection()  # get the index of the double-clicked line, if any
        if not selection:  # if nothing is actually selected
            return  # do nothing
        product_id = product_id_map[selection[0]]  # look up the real product_id for that line
        open_edit_product_window(product_id, menu_window, listbox, product_id_map, selection[0])  # open the edit popup

    listbox.bind("<Double-Button-1>", on_row_double_clicked)  # run on_row_double_clicked() whenever a line is DOUBLE-clicked


def open_edit_product_window(product_id, menu_window, listbox, product_id_map, list_index):
    connection = get_connection()  # open a connection
    cursor = connection.cursor()  # create a cursor
    cursor.execute("SELECT product_name, dish_description FROM MenuProducts WHERE product_id = ?", (product_id,))  # get this product's current info
    product_name, dish_description = cursor.fetchone()  # unpack the single matching row
    connection.close()  # close the connection

    edit_window = tk.Toplevel(menu_window)  # a new pop-up window for editing
    edit_window.title(f"Edit {product_id}")  # set its title bar text
    edit_window.geometry("350x300")  # set its size

    tk.Label(edit_window, text="Product Name:").pack(anchor="w", padx=20, pady=(15, 0))  # label
    name_entry = tk.Entry(edit_window, width=35)  # text box for the product name
    name_entry.insert(0, product_name)  # pre-fill it with the current name
    name_entry.pack(padx=20, pady=(0, 10))  # place it

    tk.Label(edit_window, text="Dish Description:").pack(anchor="w", padx=20)  # label
    description_entry = tk.Entry(edit_window, width=35)  # text box for the description
    description_entry.insert(0, dish_description or "")  # pre-fill it with the current description
    description_entry.pack(padx=20, pady=(0, 10))  # place it

    message_label = tk.Label(edit_window, text="", fg="red")  # a label for error messages
    message_label.pack(pady=5)  # place it

    def save_changes():
        new_name = name_entry.get().strip()  # read the typed name
        new_description = description_entry.get().strip()  # read the typed description
        if new_name == "":  # a product must have a name
            message_label.config(text="Product Name cannot be empty.")  # show an error
            return  # stop here
        connection2 = get_connection()  # open a fresh connection for saving
        cursor2 = connection2.cursor()  # create a cursor
        cursor2.execute("UPDATE MenuProducts SET product_name = ?, dish_description = ? WHERE product_id = ?",
                         (new_name, new_description if new_description != "" else None, product_id))  # save the changes
        connection2.commit()  # save permanently
        connection2.close()  # close the connection

        listbox.delete(list_index)  # remove the old line from the list
        listbox.insert(list_index, f"{new_name} - {new_description or '(no description)'}")  # insert the updated line in the same spot
        edit_window.destroy()  # close this edit window

    tk.Button(edit_window, text="Save", command=save_changes, bg="#4CAF50", fg="white",
              font=("Arial", 13, "bold"), width=15, height=2).pack(pady=15)  # the enlarged save button


# ---------------------------------------------------------------------------
# EXTRAS WINDOW (add a new add-on product)
# ---------------------------------------------------------------------------

def open_extras_window():
    extras_window = tk.Toplevel(window)  # a new pop-up window
    extras_window.title("Insert a new Addon")  # set its title bar text
    extras_window.geometry("400x500")  # set its starting size (the scrollbar handles any overflow)

    canvas5 = tk.Canvas(extras_window)  # a scrollable drawing surface - our form goes inside it
    scrollbar5 = tk.Scrollbar(extras_window, orient="vertical", command=canvas5.yview)  # a vertical scrollbar linked to the canvas
    form_frame5 = tk.Frame(canvas5)  # the frame that will actually hold every field and the Save button
    form_frame5.bind("<Configure>", lambda event: canvas5.configure(scrollregion=canvas5.bbox("all")))  # keep the scroll area updated
    canvas5.create_window((0, 0), window=form_frame5, anchor="nw")  # place form_frame5 inside the canvas
    canvas5.configure(yscrollcommand=scrollbar5.set)  # connect the canvas's vertical position to the scrollbar
    canvas5.pack(side="left", fill="both", expand=True)  # place the canvas, filling remaining space
    scrollbar5.pack(side="right", fill="y")  # place the scrollbar along the right edge

    def on_mousewheel_extras(event):
        canvas5.yview_scroll(-1 * (event.delta // 120), "units")  # scroll the canvas up/down with the mouse wheel
    canvas5.bind_all("<MouseWheel>", on_mousewheel_extras)  # activate mouse wheel scrolling over this window

    tk.Label(form_frame5, text="Insert a new Addon", font=("Arial", 14, "bold")).pack(pady=15)  # heading

    connection = get_connection()  # open a connection
    cursor = connection.cursor()  # create a cursor
    new_id = next_product_id(cursor)  # figure out the next available product_id
    connection.close()  # close the connection

    tk.Label(form_frame5, text=f"Product ID (auto): {new_id}", font=("Arial", 10, "bold")).pack(pady=(0, 10))  # shown, not editable

    def add_readonly_field(label_text, value_text):
        tk.Label(form_frame5, text=label_text).pack(anchor="w", padx=30)  # the field's label
        tk.Label(form_frame5, text=value_text, fg="gray").pack(anchor="w", padx=30, pady=(0, 8))  # the fixed, non-editable value

    add_readonly_field("Meal Type (auto):", "Any Meal")  # always "Any Meal" for add-ons
    add_readonly_field("Category (auto):", "addons")  # always "addons" for add-ons
    add_readonly_field("Meal Type Price (auto):", "(none)")  # always NULL for add-ons

    def add_editable_field(label_text):
        tk.Label(form_frame5, text=label_text).pack(anchor="w", padx=30)  # the field's label
        entry = tk.Entry(form_frame5, width=30)  # the field's text box
        entry.pack(padx=30, pady=(0, 8))  # place it
        return entry  # give back the entry box so we can read its value later

    name_entry = add_editable_field("Product Name *")  # required field
    description_entry = add_editable_field("Dish Description *")  # required field
    price_entry = add_editable_field("Add-on Price (integer) *")  # required field
    notes_entry = add_editable_field("Menu Notes (up to 200 characters)")  # optional field

    message_label = tk.Label(form_frame5, text="", fg="red", wraplength=320)  # a label for error/success messages
    message_label.pack(pady=5)  # place it

    def save_addon():
        product_name = name_entry.get().strip()  # read the typed name
        dish_description = description_entry.get().strip()  # read the typed description
        price_text = price_entry.get().strip()  # read the typed price
        menu_notes = notes_entry.get().strip()  # read the typed notes

        if product_name == "":  # product name is required
            message_label.config(text="Product Name is required.")
            return  # stop here
        if dish_description == "":  # dish description is required
            message_label.config(text="Dish Description is required.")
            return  # stop here
        if not price_text.isdigit():  # isdigit() checks it's a whole number with no minus sign or decimal point
            message_label.config(text="Add-on Price must be a whole number.")
            return  # stop here
        if len(menu_notes) > 200:  # menu notes has a maximum length of 200 characters
            message_label.config(text="Menu Notes must be 200 characters or fewer.")
            return  # stop here

        connection2 = get_connection()  # open a fresh connection for saving
        cursor2 = connection2.cursor()  # create a cursor
        generated_id = next_product_id(cursor2)  # re-check the next free ID right before saving, in case something changed
        try:
            cursor2.execute("""
                INSERT INTO MenuProducts (product_id, product_name, meal_type, category,
                                           dish_description, meal_type_price, addons_price, menu_notes)
                VALUES (?, ?, 'Any Meal', 'addons', ?, NULL, ?, ?)
            """, (generated_id, product_name, dish_description, int(price_text), menu_notes if menu_notes != "" else None))  # insert the new add-on
            connection2.commit()  # save permanently
            message_label.config(fg="green", text=f"Add-on {generated_id} saved successfully!")  # show a success message
        except sqlite3.IntegrityError as error:  # this catches any database rule violations
            message_label.config(fg="red", text=f"Could not save: {error}")  # show the database's error message
        finally:
            connection2.close()  # close the connection either way

    tk.Button(form_frame5, text="Save Addon", command=save_addon, bg="#4CAF50", fg="white", font=("Arial", 11, "bold")).pack(pady=15)  # save button


# ---------------------------------------------------------------------------
# FEEDBACK WINDOW
# ---------------------------------------------------------------------------

def open_feedback_window():
    feedback_window = tk.Toplevel(window)  # a new pop-up window
    feedback_window.title("Write a FeedBack")  # set its title bar text (matching the requested header)
    feedback_window.geometry("400x500")  # set its starting size (the scrollbar handles any overflow)

    canvas6 = tk.Canvas(feedback_window)  # a scrollable drawing surface - our form goes inside it
    scrollbar6 = tk.Scrollbar(feedback_window, orient="vertical", command=canvas6.yview)  # a vertical scrollbar linked to the canvas
    form_frame6 = tk.Frame(canvas6)  # the frame that will actually hold every field and the Submit button
    form_frame6.bind("<Configure>", lambda event: canvas6.configure(scrollregion=canvas6.bbox("all")))  # keep the scroll area updated
    canvas6.create_window((0, 0), window=form_frame6, anchor="nw")  # place form_frame6 inside the canvas
    canvas6.configure(yscrollcommand=scrollbar6.set)  # connect the canvas's vertical position to the scrollbar
    canvas6.pack(side="left", fill="both", expand=True)  # place the canvas, filling remaining space
    scrollbar6.pack(side="right", fill="y")  # place the scrollbar along the right edge

    def on_mousewheel_feedback(event):
        canvas6.yview_scroll(-1 * (event.delta // 120), "units")  # scroll the canvas up/down with the mouse wheel
    canvas6.bind_all("<MouseWheel>", on_mousewheel_feedback)  # activate mouse wheel scrolling over this window

    tk.Label(form_frame6, text="Write a FeedBack", font=("Arial", 14, "bold")).pack(pady=15)  # heading

    def add_field(label_text):
        tk.Label(form_frame6, text=label_text).pack(anchor="w", padx=30)  # the field's label
        entry = tk.Entry(form_frame6, width=25)  # the field's text box
        entry.pack(padx=30, pady=(0, 8))  # place it with spacing
        return entry  # give back the entry box so we can read its value later

    event_id_entry = add_field("Event ID *")  # required field

    email_frame = tk.Frame(form_frame6)  # a frame to hold the looked-up email + copy button together
    email_frame.pack(anchor="w", padx=30, pady=(0, 8))  # place it right under the Event ID field
    email_label = tk.Label(email_frame, text="", font=("Arial", 9), fg="#333333")  # shows the customer's email once found
    email_label.pack(side="left")  # place it on the left

    def copy_email_clicked():
        email_text = email_label.cget("text").replace("Email: ", "")  # strip our own "Email: " prefix back off before copying
        if email_text:  # only copy if there's actually an email showing
            copy_to_clipboard(email_text)  # copy it to the clipboard

    copy_email_button = tk.Button(email_frame, text="📋 Copy Email", command=copy_email_clicked)  # the copy button (hidden until an email is found)

    def lookup_email(event=None):
        # runs whenever the admin finishes typing/tabs away from the Event ID field - looks up and shows the customer's email
        event_id_text = event_id_entry.get().strip()  # read the event ID field
        if not event_id_text.isdigit():  # if it's not a valid whole number yet
            email_label.config(text="")  # clear any previously shown email
            copy_email_button.pack_forget()  # hide the copy button
            return  # stop here, nothing to look up
        connection = get_connection()  # open a connection
        cursor = connection.cursor()  # create a cursor
        cursor.execute("""
            SELECT Customers.email FROM Events JOIN Customers ON Events.customer_id = Customers.customer_id
            WHERE Events.event_id = ?
        """, (int(event_id_text),))  # find the email of the customer linked to this event
        result = cursor.fetchone()  # get the single matching row, or None if this event doesn't exist
        connection.close()  # close the connection
        if result is None:  # if no event with this ID exists
            email_label.config(text="(no matching event)")  # show a small explanation
            copy_email_button.pack_forget()  # hide the copy button
        else:  # otherwise, show the email and the copy button
            email_label.config(text=f"Email: {result[0]}")  # display the customer's email
            copy_email_button.pack(side="left", padx=(8, 0))  # show the copy button next to it

    event_id_entry.bind("<FocusOut>", lookup_email)  # look up the email when the admin clicks/tabs away from the field
    event_id_entry.bind("<Return>", lookup_email)  # or when they press Enter while still in the field

    overall_entry = add_field("Overall Rating (1-5)")  # optional field
    food_entry = add_field("Food Rating (1-5)")  # optional field
    service_entry = add_field("Service Rating (1-5)")  # optional field
    recommend_entry = add_field("Would Recommend (1-5)")  # optional field
    comments_entry = add_field("Comments (up to 20 characters)")  # optional field

    message_label = tk.Label(form_frame6, text="", fg="red", wraplength=300)  # a label for error/success messages
    message_label.pack(pady=5)  # place it

    def parse_optional_rating(text, field_name):
        # returns None if the field was left blank, the number if valid, or raises ValueError if invalid
        text = text.strip()  # remove any accidental extra spaces
        if text == "":  # if nothing was typed
            return None  # treat it as "no value given"
        if not text.isdigit() or not (1 <= int(text) <= 5):  # must be a whole number from 1 to 5
            raise ValueError(f"{field_name} must be a whole number between 1 and 5, or left blank.")  # explain what went wrong
        return int(text)  # convert and return the valid number

    def submit_feedback():
        event_id_text = event_id_entry.get().strip()  # read the event ID field
        if not event_id_text.isdigit():  # event_id is required and must be a whole number
            message_label.config(text="Event ID is required and must be a whole number.")  # show an error
            return  # stop here
        event_id = int(event_id_text)  # convert it to a real integer

        connection = get_connection()  # open a connection
        cursor = connection.cursor()  # create a cursor
        cursor.execute("SELECT COUNT(*) FROM Events WHERE event_id = ?", (event_id,))  # check this event actually exists
        exists = cursor.fetchone()[0] > 0  # True if we found a matching event
        if not exists:  # if no such event exists
            message_label.config(text=f"No event with ID {event_id} exists.")  # show an error
            connection.close()  # close the connection since we're stopping
            return  # stop here

        try:
            overall_rating = parse_optional_rating(overall_entry.get(), "Overall Rating")  # validate/parse each rating field
            food_rating = parse_optional_rating(food_entry.get(), "Food Rating")
            service_rating = parse_optional_rating(service_entry.get(), "Service Rating")
            would_recommend = parse_optional_rating(recommend_entry.get(), "Would Recommend")
        except ValueError as error:  # this happens if any rating was invalid
            message_label.config(text=str(error))  # show the specific error message
            connection.close()  # close the connection since we're stopping
            return  # stop here

        comments = comments_entry.get().strip()  # read the comments field
        if len(comments) > 20:  # comments has a maximum length of 20 characters
            message_label.config(text="Comments must be 20 characters or fewer.")  # show an error
            connection.close()  # close the connection since we're stopping
            return  # stop here
        comments_value = comments if comments != "" else None  # store as None if left blank

        feedback_date = datetime.date.today().strftime("%Y/%m/%d")  # today's date, formatted YYYY/MM/DD as requested

        try:
            cursor.execute("""
                INSERT INTO Feedback (event_id, overall_rating, food_rating, service_rating,
                                       would_recommend, comments, feedback_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (event_id, overall_rating, food_rating, service_rating, would_recommend, comments_value, feedback_date))  # save the feedback
            connection.commit()  # save the change permanently
            message_label.config(fg="green", text="Feedback saved. Thank you!")  # show a success message
        except sqlite3.IntegrityError as error:  # this catches any database rule violations
            message_label.config(fg="red", text=f"Could not save: {error}")  # show the database's error message
        finally:
            connection.close()  # close the connection either way

    tk.Button(form_frame6, text="Submit Feedback", command=submit_feedback, bg="#4CAF50", fg="white",
              font=("Arial", 13, "bold"), width=20, height=2).pack(pady=15)  # the enlarged submit button


# ---------------------------------------------------------------------------
# INCOME CHART (last 10 days)
# ---------------------------------------------------------------------------

def build_income_chart():
    # this function draws (or redraws) the income bar chart from scratch, using the latest data
    for widget in chart_frame.winfo_children():  # loop through every widget currently in the chart frame
        widget.destroy()  # remove it (the old chart), so we can draw a fresh one

    connection = get_connection()  # open a connection
    cursor = connection.cursor()  # create a cursor
    last_10_days = get_last_10_days_income(cursor, datetime.date.today())  # get the last 10 days' income figures
    connection.close()  # close the connection

    chart_dates = [day.strftime("%d/%m") for day, income in last_10_days]  # build the x-axis labels
    chart_income = [income for day, income in last_10_days]  # build the y-axis values

    figure = plt.Figure(figsize=(7, 3), dpi=100)  # create a new blank chart, 7x3 inches
    plot = figure.add_subplot(111)  # add a single set of axes to draw on
    plot.bar(chart_dates, chart_income, color="#2196F3")  # draw the vertical bar chart
    plot.set_ylabel("₪")  # label the vertical axis with the currency symbol
    plot.set_title("Last 10 Days Income")  # title for the chart

    chart_canvas = FigureCanvasTkAgg(figure, master=chart_frame)  # embed the matplotlib chart inside our chart_frame
    chart_canvas.draw()  # render the chart
    chart_canvas.get_tk_widget().pack()  # place the chart's drawing area in the window


tk.Label(main_frame, text="INCOME", font=("Arial", 14, "bold")).pack(pady=(20, 5))  # chart heading

chart_frame = tk.Frame(main_frame)  # a frame to hold the income chart, so REFRESH can rebuild it in place
chart_frame.pack(pady=10)  # place it below the heading

build_income_chart()  # draw the chart for the first time when the dashboard opens

# ---------------------------------------------------------------------------
# FOOTER
# ---------------------------------------------------------------------------

def open_new_request_screen_clicked():
    subprocess.Popen([sys.executable, "new_request_screen.py"])  # launch the New Event Request form as its own separate program,
    # so it runs alongside the Dashboard instead of needing its own manually-opened terminal


tk.Button(main_frame, text="New Event Request", command=open_new_request_screen_clicked,
          font=("Arial", 9), bg="#E0E0E0").pack(pady=(5, 5))  # a small button, tucked in near the bottom

tk.Label(main_frame, text="Now, let's get to work !", font=("Arial", 12, "italic")).pack(pady=(10, 30))  # closing message

window.mainloop()  # start the GUI event loop - keeps the window open and responsive until closed
