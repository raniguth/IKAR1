# ikalendar.py
# PURPOSE OF THIS FILE:
# This file builds "Ikalendar" - a week-view calendar window that shows which
# dates/times are free, partly booked, or fully booked. It opens as a pop-up
# window when the admin clicks the "Please Check our Calendar for Availability
# date and time" button on the New Event Request screen.

import tkinter as tk  # import the GUI library, nicknamed "tk"
import sqlite3  # import the library that lets Python talk to the SQLite database
import datetime  # import the library that helps us work with dates and times

SLOT_HOURS = list(range(8, 22))  # the fixed hourly slots we display: 8 (08:00) through 21 (21:00-22:00), covering our widest opening hours
DAY_NAMES_SHORT = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]  # short display labels for the 7 column headers

# ---------------------------------------------------------------------------
# DATABASE / LOGIC HELPER FUNCTIONS
# These are separate from the GUI-drawing code, and were tested independently
# ---------------------------------------------------------------------------

def get_week_start(reference_date):
    # returns the Sunday date of the week containing reference_date
    days_since_sunday = (reference_date.weekday() + 1) % 7  # weekday(): Monday=0 .. Sunday=6, this converts to "days since Sunday"
    return reference_date - datetime.timedelta(days=days_since_sunday)  # subtract that many days to land on Sunday


def fetch_opening_hours(cursor):
    # returns a dictionary like {"Sunday": ("08:00","22:00"), "Saturday": (None,None), ...}
    cursor.execute("SELECT day_of_week, open_time, close_time FROM OpeningHours")  # get every day's hours
    return {day: (open_t, close_t) for day, open_t, close_t in cursor.fetchall()}  # build the dictionary from the rows


def fetch_events_for_week(cursor, week_start, week_end):
    # returns every booked (Accepted -> now an Event) booking that falls within this week, with the customer's first name
    cursor.execute("""
        SELECT Events.event_date, Events.event_start_time, Events.event_end_time,
               Events.num_guests, Customers.first_name
        FROM Events JOIN Customers ON Events.customer_id = Customers.customer_id
        WHERE Events.event_date BETWEEN ? AND ?
    """, (week_start.isoformat(), week_end.isoformat()))  # find events between the Sunday and the following Saturday
    return cursor.fetchall()  # return every matching row


def fetch_capacity(cursor):
    # returns the restaurant's total guest capacity from the Settings table
    cursor.execute("SELECT total_capacity FROM Settings LIMIT 1")  # get the one settings row
    return cursor.fetchone()[0]  # extract the number


def compute_cell(day_date, slot_start, slot_end, opening_hours, week_events, capacity):
    # this function decides what one grid cell (one day, one hour) should show and what color it should be
    day_name = day_date.strftime("%A")  # get the full weekday name, e.g. "Wednesday"
    open_time, close_time = opening_hours.get(day_name, (None, None))  # look up this day's opening hours
    if open_time is None or not (slot_start < close_time and slot_end > open_time):  # if closed, or this hour falls outside opening hours
        return {"closed": True}  # mark this cell as closed - it will be drawn grey with no booking info
    matches = [e for e in week_events if e[0] == day_date.isoformat() and e[1] < slot_end and e[2] > slot_start]  # find events overlapping this exact hour
    total_guests = sum(e[3] for e in matches)  # add up all the guests from every overlapping event
    names = [f"{e[4]} ({e[3]})" for e in matches]  # build a list like ["Yossi (100)", "Ronit (60)"]
    if total_guests == 0:  # if nobody is booked in this slot
        color = "white"  # white means fully free
    elif total_guests < capacity:  # if some guests are booked but there's still room
        color = "#FFD6E8"  # light pink means partially booked
    else:  # if the booked guests meet or exceed capacity
        color = "#FF6B6B"  # red means fully booked, no more room
    return {"closed": False, "color": color, "names": names, "total_guests": total_guests, "free": capacity - total_guests}


# ---------------------------------------------------------------------------
# GUI: THE CALENDAR WINDOW
# ---------------------------------------------------------------------------

def open_calendar(parent, allow_past_weeks=False):
    # this is the main function other files call to pop open the Ikalendar window
    # allow_past_weeks=False (the default) is for the customer-facing "check availability" button,
    # which should never be able to browse into past weeks
    # allow_past_weeks=True is for the admin's own calendar, which CAN browse into past weeks
    today = datetime.date.today()  # get today's real date
    current_week_start = get_week_start(today)  # figure out the Sunday of the current week - navigation can never go earlier than this
    displayed_week_start = current_week_start  # this variable tracks which week is currently being shown, starts on the current week

    calendar_window = tk.Toplevel(parent)  # Toplevel creates a new pop-up window on top of the parent window
    calendar_window.title("Ikalendar - Availability Calendar")  # set the pop-up window's title bar text
    calendar_window.geometry("1000x600")  # set the starting size of the pop-up window

    top_frame = tk.Frame(calendar_window)  # a frame to hold the navigation buttons and week label
    top_frame.pack(pady=10)  # place it at the top with some spacing

    prev_button = tk.Button(top_frame, text="< Previous Week")  # the button to go back a week (command is set further down)
    prev_button.grid(row=0, column=0, padx=10)  # place it on the left

    week_label = tk.Label(top_frame, text="", font=("Arial", 12, "bold"))  # a label showing the currently displayed date range
    week_label.grid(row=0, column=1, padx=20)  # place it in the middle

    next_button = tk.Button(top_frame, text="Next Week >")  # the button to go forward a week (command is set further down)
    next_button.grid(row=0, column=2, padx=10)  # place it on the right

    legend_frame = tk.Frame(calendar_window)  # a small frame to explain the color meanings
    legend_frame.pack(pady=(0, 5))  # place it below the navigation row
    tk.Label(legend_frame, text="White = Free", bg="white", relief="solid", padx=8).pack(side="left", padx=5)  # white swatch
    tk.Label(legend_frame, text="Pink = Partially Booked", bg="#FFD6E8", relief="solid", padx=8).pack(side="left", padx=5)  # pink swatch
    tk.Label(legend_frame, text="Red = Fully Booked", bg="#FF6B6B", relief="solid", padx=8).pack(side="left", padx=5)  # red swatch
    tk.Label(legend_frame, text="Grey = Closed", bg="#CCCCCC", relief="solid", padx=8).pack(side="left", padx=5)  # grey swatch

    canvas = tk.Canvas(calendar_window)  # a Canvas is a scrollable drawing surface - our grid will live inside it
    scrollbar = tk.Scrollbar(calendar_window, orient="vertical", command=canvas.yview)  # a vertical scrollbar linked to the canvas
    grid_frame = tk.Frame(canvas)  # a frame to hold the actual day/hour grid

    grid_frame.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))  # keep the scroll area updated as the grid changes size
    canvas.create_window((0, 0), window=grid_frame, anchor="nw")  # place grid_frame inside the canvas, starting top-left
    canvas.configure(yscrollcommand=scrollbar.set)  # connect the canvas's vertical position to the scrollbar
    canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)  # place the canvas, filling remaining space
    scrollbar.pack(side="right", fill="y")  # place the scrollbar along the right edge

    def on_mousewheel(event):
        canvas.yview_scroll(-1 * (event.delta // 120), "units")  # scroll the canvas up/down when the mouse wheel is used

    canvas.bind_all("<MouseWheel>", on_mousewheel)  # activate mouse wheel scrolling anywhere over the calendar window

    def draw_week():
        # this function wipes and redraws the entire grid for whatever week is currently selected
        for widget in grid_frame.winfo_children():  # loop through every widget currently inside grid_frame
            widget.destroy()  # remove it, so we can draw the new week fresh

        week_end = displayed_week_start + datetime.timedelta(days=6)  # the Saturday that ends this week
        week_label.config(text=f"{displayed_week_start.strftime('%b %d, %Y')} - {week_end.strftime('%b %d, %Y')}")  # update the header text

        should_disable_prev = (not allow_past_weeks) and (displayed_week_start <= current_week_start)  # only block past weeks in the non-admin (customer-facing) view
        prev_button.config(state="disabled" if should_disable_prev else "normal")  # apply that rule to the button

        connection = sqlite3.connect("land_farmer.db")  # open a database connection
        cursor = connection.cursor()  # create a cursor
        opening_hours = fetch_opening_hours(cursor)  # load this restaurant's opening hours
        week_events = fetch_events_for_week(cursor, displayed_week_start, week_end)  # load every booking in this week
        capacity = fetch_capacity(cursor)  # load the restaurant's total capacity
        connection.close()  # close the connection, we have everything we need now

        tk.Label(grid_frame, text="Time", font=("Arial", 9, "bold"), width=10, relief="solid").grid(row=0, column=0, sticky="nsew")  # top-left corner cell
        for col in range(7):  # loop through the 7 days of the week, column 0 = Sunday
            day_date = displayed_week_start + datetime.timedelta(days=col)  # calculate this column's actual date
            header_text = f"{DAY_NAMES_SHORT[col]}\n{day_date.strftime('%m/%d')}"  # e.g. "Sun\n07/19"
            tk.Label(grid_frame, text=header_text, font=("Arial", 9, "bold"), width=14, relief="solid").grid(row=0, column=col + 1, sticky="nsew")  # day header

        for row, hour in enumerate(SLOT_HOURS, start=1):  # loop through every hourly time slot, row 1 is the first time row
            slot_start = f"{hour:02d}:00"  # format the hour as "08:00" style text, zero-padded
            slot_end = f"{hour + 1:02d}:00"  # the end of this hour slot
            tk.Label(grid_frame, text=f"{slot_start}-{slot_end}", font=("Arial", 8), width=10, relief="solid").grid(row=row, column=0, sticky="nsew")  # time label

            for col in range(7):  # loop through each day column again, for this specific hour row
                day_date = displayed_week_start + datetime.timedelta(days=col)  # this cell's actual date
                cell = compute_cell(day_date, slot_start, slot_end, opening_hours, week_events, capacity)  # calculate what this cell should show

                if cell["closed"]:  # if the restaurant is closed at this day/hour
                    tk.Label(grid_frame, text="Closed", bg="#CCCCCC", font=("Arial", 7), width=14, height=2, relief="solid").grid(row=row, column=col + 1, sticky="nsew")  # grey closed cell
                elif cell["total_guests"] == 0:  # if open but nobody booked
                    tk.Label(grid_frame, text="", bg="white", width=14, height=2, relief="solid").grid(row=row, column=col + 1, sticky="nsew")  # plain white free cell
                else:  # if open and at least one booking overlaps this hour
                    cell_text = ", ".join(cell["names"]) + f"\n{cell['free']} free"  # e.g. "Yossi (100)\n50 free"
                    tk.Label(grid_frame, text=cell_text, bg=cell["color"], font=("Arial", 7), width=14, height=2, relief="solid", wraplength=100).grid(row=row, column=col + 1, sticky="nsew")  # colored booked cell

    def go_previous_week():
        nonlocal displayed_week_start  # nonlocal lets us change the variable from the outer function, not create a new local one
        if allow_past_weeks or displayed_week_start > current_week_start:  # admins can always go back; others only if not already on the current week
            displayed_week_start = displayed_week_start - datetime.timedelta(days=7)  # move back 7 days
            draw_week()  # redraw the grid for the new week

    def go_next_week():
        nonlocal displayed_week_start  # again, modify the outer variable rather than making a new local one
        displayed_week_start = displayed_week_start + datetime.timedelta(days=7)  # move forward 7 days
        draw_week()  # redraw the grid for the new week

    prev_button.config(command=go_previous_week)  # now that go_previous_week exists, connect it to the button
    next_button.config(command=go_next_week)  # connect the next-week function to its button

    draw_week()  # draw the calendar for the very first time when the window opens

    return draw_week  # hand back draw_week itself, so other code (like a Dashboard Refresh button) can redraw this exact calendar later
