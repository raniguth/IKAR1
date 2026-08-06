# date_picker.py
# PURPOSE OF THIS FILE:
# This file provides a pop-up monthly calendar the client can click through
# instead of typing a date. It starts on the current month, can only move
# FORWARD to future months (never back before the current month), and marks
# closed days (like Saturday) in red so they can't be picked.

import tkinter as tk  # import the GUI library, nicknamed "tk"
import sqlite3  # import the library that lets Python talk to the SQLite database
import datetime  # import the library that helps us work with dates and times

DAY_HEADERS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]  # the column headers, Sunday first


def get_closed_day_names(cursor):
    # returns a set of weekday names (e.g. {"Saturday"}) where the restaurant is closed
    cursor.execute("SELECT day_of_week FROM OpeningHours WHERE open_time IS NULL")  # a NULL open_time means "closed"
    return {row[0] for row in cursor.fetchall()}  # build a set of just the day names


def days_in_month(year, month):
    # returns how many days are in a given month, without using the calendar module
    if month == 12:  # December needs special handling, since "next month" rolls into a new year
        first_of_next_month = datetime.date(year + 1, 1, 1)  # January 1st of next year
    else:  # every other month
        first_of_next_month = datetime.date(year, month + 1, 1)  # the 1st of the following month
    first_of_this_month = datetime.date(year, month, 1)  # the 1st of the current month
    return (first_of_next_month - first_of_this_month).days  # the gap between them is exactly how many days this month has


def open_date_picker(parent, on_date_selected, earliest_selectable_date):
    # this is the main function other files call to pop open the calendar
    # on_date_selected: a function to call with the chosen date once the client picks one
    # earliest_selectable_date: the first date allowed to be picked (e.g. tomorrow) - nothing before this can be chosen

    connection = sqlite3.connect("land_farmer.db")  # open a connection
    cursor = connection.cursor()  # create a cursor
    closed_day_names = get_closed_day_names(cursor)  # find out which weekdays are closed
    connection.close()  # close the connection, we have what we need

    picker_window = tk.Toplevel(parent)  # Toplevel creates a new pop-up window on top of the parent window
    picker_window.title("Select Event Date")  # set the pop-up window's title bar text
    picker_window.geometry("320x320")  # set the starting size of the pop-up window

    state = {"year": earliest_selectable_date.year, "month": earliest_selectable_date.month}  # tracks which month is currently displayed

    header_frame = tk.Frame(picker_window)  # a frame to hold the "< Month YYYY >" navigation row
    header_frame.pack(pady=10)  # place it at the top

    prev_button = tk.Button(header_frame, text="<")  # the "go to previous month" button (command is set further down)
    prev_button.grid(row=0, column=0, padx=10)  # place it on the left

    month_label = tk.Label(header_frame, text="", font=("Arial", 12, "bold"), width=15)  # shows the currently displayed "Month YYYY"
    month_label.grid(row=0, column=1)  # place it in the middle

    next_button = tk.Button(header_frame, text=">")  # the "go to next month" button (command is set further down)
    next_button.grid(row=0, column=2, padx=10)  # place it on the right

    grid_frame = tk.Frame(picker_window)  # a frame to hold the actual day-number grid
    grid_frame.pack(pady=10)  # place it below the navigation row

    def draw_month():
        # this function wipes and redraws the entire day grid for whatever month is currently selected
        for widget in grid_frame.winfo_children():  # loop through every widget currently in the grid
            widget.destroy()  # remove it, so we can draw the new month fresh

        year, month = state["year"], state["month"]  # read the currently displayed year/month
        month_name = datetime.date(year, month, 1).strftime("%B")  # get the full month name, e.g. "August"
        month_label.config(text=f"{month_name} {year}")  # update the header text

        is_at_earliest_month = (year == earliest_selectable_date.year and month == earliest_selectable_date.month)  # are we as far back as allowed?
        prev_button.config(state="disabled" if is_at_earliest_month else "normal")  # block going earlier than the starting month

        for col, day_name in enumerate(DAY_HEADERS):  # loop through the 7 weekday headers
            tk.Label(grid_frame, text=day_name, font=("Arial", 9, "bold"), width=4).grid(row=0, column=col)  # place each header

        first_of_month = datetime.date(year, month, 1)  # the 1st day of this month
        start_column = (first_of_month.weekday() + 1) % 7  # convert Python's Monday=0 weekday into "columns after Sunday"
        total_days = days_in_month(year, month)  # how many days this month has

        row = 1  # start placing day buttons on the row right below the headers
        col = start_column  # start placing the 1st of the month at its correct weekday column
        for day_number in range(1, total_days + 1):  # loop through every day number in this month
            this_date = datetime.date(year, month, day_number)  # build the actual date for this day
            day_name = this_date.strftime("%A")  # get this date's full weekday name

            if this_date < earliest_selectable_date:  # if this date is before the earliest allowed date
                tk.Label(grid_frame, text=str(day_number), width=4, fg="gray").grid(row=row, column=col, padx=1, pady=1)  # show it greyed out, not clickable
            elif day_name in closed_day_names:  # if the restaurant is closed on this date
                tk.Label(grid_frame, text=str(day_number), width=4, fg="white", bg="#E53935").grid(row=row, column=col, padx=1, pady=1)  # show it in red, not clickable
            else:  # otherwise, this is a valid, pickable date
                tk.Button(grid_frame, text=str(day_number), width=3,
                          command=lambda d=this_date: pick_date(d)).grid(row=row, column=col, padx=1, pady=1)  # a real clickable button

            col += 1  # move to the next column
            if col > 6:  # if we've filled a full week (columns 0-6)
                col = 0  # wrap back around to Sunday's column
                row += 1  # and move down to the next row

    def pick_date(chosen_date):
        on_date_selected(chosen_date)  # tell the caller which date was picked
        picker_window.destroy()  # close the calendar pop-up

    def go_previous_month():
        if state["month"] == 1:  # January wraps back to December of the previous year
            state["year"] -= 1  # go back one year
            state["month"] = 12  # land on December
        else:  # any other month just goes back by one
            state["month"] -= 1  # move back one month
        draw_month()  # redraw the grid for the new month

    def go_next_month():
        if state["month"] == 12:  # December wraps forward to January of the next year
            state["year"] += 1  # go forward one year
            state["month"] = 1  # land on January
        else:  # any other month just goes forward by one
            state["month"] += 1  # move forward one month
        draw_month()  # redraw the grid for the new month

    prev_button.config(command=go_previous_month)  # connect the previous-month button to its function
    next_button.config(command=go_next_month)  # connect the next-month button to its function

    draw_month()  # draw the calendar for the very first time when the window opens
