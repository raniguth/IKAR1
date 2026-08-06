# update_request_status.py
# PURPOSE OF THIS FILE:
# This file shows a window listing every Request. You select one, see its
# details (including its meal option and quoted price, if the client already
# went through "Build Your Menu"), and change its status using a dropdown.
# If you change the status to "Accepted", the app automatically copies that
# Request's information (and chosen products) into a brand new row in the
# Events table - the same automation that "Build Your Menu" also triggers
# when the client confirms directly.

import tkinter as tk  # import the GUI library, nicknamed "tk"
from tkinter import messagebox  # import the pop-up message box part of tkinter
import sqlite3  # import the library that lets Python talk to the SQLite database

STATUS_OPTIONS = ["New Inquiry", "Quoted", "Accepted", "Declined"]  # the only 4 allowed values, matching our database CHECK rule

# ---------------------------------------------------------------------------
# DATABASE HELPER FUNCTIONS
# ---------------------------------------------------------------------------

def get_connection():
    return sqlite3.connect("land_farmer.db")  # open (and return) a fresh connection to our database file


def load_all_requests():
    # this function pulls every request, joined with the customer's name, so the list is readable
    connection = get_connection()  # open a connection
    cursor = connection.cursor()  # create a cursor to run commands with
    cursor.execute("""
        SELECT Requests.request_number, Customers.first_name, Customers.last_name,
               Requests.requested_event_date, Requests.requested_start_time,
               Requests.num_guests, Requests.status
        FROM Requests
        JOIN Customers ON Requests.customer_id = Customers.customer_id
        ORDER BY Requests.request_number
    """)  # JOIN combines the Requests table with the Customers table, matching on customer_id
    rows = cursor.fetchall()  # fetchall() gets every matching row as a list
    connection.close()  # close the connection since we're done reading
    return rows  # give back the list of rows


def load_request_details(request_number):
    # this function pulls every column for one specific request, so we can show it and edit it
    connection = get_connection()  # open a connection
    cursor = connection.cursor()  # create a cursor
    cursor.execute("SELECT * FROM Requests WHERE request_number = ?", (request_number,))  # find the one matching row
    columns = [description[0] for description in cursor.description]  # description holds column names, pull just the names out
    row = cursor.fetchone()  # fetchone() gets that single row
    connection.close()  # close the connection
    return dict(zip(columns, row))  # zip() pairs each column name with its value, dict() turns that into a lookup dictionary


def load_chosen_products(request_number):
    # this function returns the product names this request has selected (via Build Your Menu), if any
    connection = get_connection()  # open a connection
    cursor = connection.cursor()  # create a cursor
    cursor.execute("""
        SELECT MenuProducts.product_name FROM RequestProducts
        JOIN MenuProducts ON RequestProducts.product_id = MenuProducts.product_id
        WHERE RequestProducts.request_number = ?
    """, (request_number,))  # find every product chosen for this request
    names = [row[0] for row in cursor.fetchall()]  # pull just the names out of each row
    connection.close()  # close the connection
    return names  # give back the list of product names


def event_already_exists_for_request(cursor, request_number):
    # this function checks whether this request was already turned into an event before,
    # so we don't accidentally create a duplicate event
    cursor.execute("SELECT COUNT(*) FROM Events WHERE request_number = ?", (request_number,))  # count matching events
    count = cursor.fetchone()[0]  # get the count out of the result
    return count > 0  # return True if one or more matching events already exist


def create_event_from_request(cursor, request_details):
    # this function copies a Request's information into a brand new Events row,
    # then copies its chosen products (RequestProducts) onto the new event too
    cursor.execute("""
        INSERT INTO Events (request_number, customer_id, event_date, event_start_time, event_end_time,
                             num_guests, event_type, dietary_restrictions, special_requests, notes,
                             meal_option, total_price)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        request_details["request_number"], request_details["customer_id"],
        request_details["requested_event_date"], request_details["requested_start_time"],
        request_details["requested_end_time"], request_details["num_guests"],
        request_details["event_type"], request_details["dietary_restrictions"],
        request_details["special_requests"], request_details["notes"],
        request_details["meal_option"], request_details["quoted_total_price"]
    ))  # insert the new event row (status defaults to 'Confirmed', deposit fields stay empty, as we designed)
    event_id = cursor.lastrowid  # lastrowid gives us the event_id that SQLite just auto-generated

    cursor.execute("SELECT product_id FROM RequestProducts WHERE request_number = ?", (request_details["request_number"],))  # get chosen products
    for (product_id,) in cursor.fetchall():  # loop through each one (each row is a 1-item tuple, hence the comma)
        cursor.execute("INSERT INTO EventProducts (event_id, product_id) VALUES (?, ?)", (event_id, product_id))  # copy it onto the event


# ---------------------------------------------------------------------------
# GUI SETUP
# ---------------------------------------------------------------------------

window = tk.Tk()  # create the main application window
window.title("Land Farmer - Update Request Status")  # set the window's title bar text
window.geometry("650x600")  # set the starting window size

tk.Label(window, text="All Requests", font=("Arial", 14, "bold")).pack(pady=10)  # heading label

request_listbox = tk.Listbox(window, width=90, height=12)  # a scrollable list box showing one line per request
request_listbox.pack(padx=15, pady=5)  # place the listbox with some spacing

request_number_map = []  # this list will remember which request_number belongs to each line in the listbox


def refresh_list():
    request_listbox.delete(0, tk.END)  # clear every existing line from the listbox
    request_number_map.clear()  # clear our memory of which request_number is on which line
    for row in load_all_requests():  # loop through every request returned from the database
        request_number, first_name, last_name, event_date, start_time, num_guests, status = row  # unpack the tuple into named variables
        line = f"#{request_number} | {first_name} {last_name} | {event_date} {start_time} | {num_guests} guests | Status: {status}"  # build a readable line of text
        request_listbox.insert(tk.END, line)  # add that line to the bottom of the listbox
        request_number_map.append(request_number)  # remember this line's real request_number, in the same order


details_frame = tk.Frame(window)  # a container to hold the "selected request" details and controls
details_frame.pack(pady=10, fill="x", padx=15)  # place the container below the listbox

selected_label = tk.Label(details_frame, text="Select a request above to update it.", font=("Arial", 10, "italic"))  # instructions
selected_label.pack(anchor="w")  # place the instructions, left-aligned

quote_info_label = tk.Label(details_frame, text="", font=("Arial", 10), fg="#333333", justify="left", wraplength=580)  # shows the meal option, quote, and chosen products (read-only)
quote_info_label.pack(anchor="w", pady=(5, 10))  # place it below the heading

tk.Label(details_frame, text="New Status:").pack(anchor="w", pady=(5, 0))  # label for the status dropdown
status_var = tk.StringVar(window)  # a special tkinter variable that holds the dropdown's current value
status_var.set(STATUS_OPTIONS[0])  # set a starting default value
status_dropdown = tk.OptionMenu(details_frame, status_var, *STATUS_OPTIONS)  # the dropdown menu itself, built from our allowed list
status_dropdown.pack(anchor="w")  # place the dropdown

status_message = tk.Label(details_frame, text="", fg="red", wraplength=580)  # a label to show success/error messages
status_message.pack(anchor="w", pady=10)  # place the message label

current_request_number = tk.IntVar(window, value=0)  # remembers which request_number is currently selected (0 = none)


def on_request_selected(event):
    selection = request_listbox.curselection()  # curselection() returns the index of the clicked line, if any
    if not selection:  # if nothing is actually selected (e.g. an empty click)
        return  # do nothing
    index = selection[0]  # get the index number of the selected line
    request_number = request_number_map[index]  # look up the real request_number for that line
    current_request_number.set(request_number)  # remember it for when the Update button is clicked
    details = load_request_details(request_number)  # load every column for this request
    selected_label.config(text=f"Editing Request #{request_number} - {details['event_type'] or '(no event type)'} on {details['requested_event_date']}")  # update the heading
    status_var.set(details["status"])  # set the status dropdown to match the current status

    if details["quoted_total_price"] is None:  # if no quote has been generated yet for this request
        quote_info_label.config(text="No quote yet - use 'Build Your Menu' on the New Event Request form to generate one.")  # explain what's missing
    else:  # otherwise, show the existing quote details
        products = load_chosen_products(request_number)  # get the list of chosen product names
        products_text = ", ".join(products) if products else "(none)"  # join them into one readable line
        quote_info_label.config(text=f"Meal option: {details['meal_option']}   |   Quoted price: ₪{details['quoted_total_price']:,.2f}\nChosen products: {products_text}")  # show everything

    status_message.config(text="")  # clear any old success/error message


request_listbox.bind("<<ListboxSelect>>", on_request_selected)  # run on_request_selected() whenever the user clicks a line


def update_status():
    request_number = current_request_number.get()  # get the currently selected request_number
    if request_number == 0:  # if nothing has been selected yet
        status_message.config(fg="red", text="Please select a request from the list first.")  # show an error
        return  # stop here

    new_status = status_var.get()  # read the chosen status from the dropdown

    connection = get_connection()  # open a connection
    cursor = connection.cursor()  # create a cursor

    if new_status == "Accepted":  # extra rules apply when moving a request to Accepted
        cursor.execute("SELECT quoted_total_price FROM Requests WHERE request_number = ?", (request_number,))  # check for an existing quote
        quoted_price = cursor.fetchone()[0]  # get that value out of the result
        if quoted_price is None:  # a quote must already exist before we can accept
            status_message.config(fg="red", text="This request has no quote yet. Use 'Build Your Menu' on the New Event Request form first.")
            connection.close()  # close the connection since we're stopping
            return  # stop here
        if event_already_exists_for_request(cursor, request_number):  # check we haven't already created an event for this request
            status_message.config(fg="red", text="An event already exists for this request.")  # show error
            connection.close()  # close the connection since we're stopping
            return  # stop here

    cursor.execute("UPDATE Requests SET status = ? WHERE request_number = ?", (new_status, request_number))  # save the new status

    if new_status == "Accepted":  # if we just accepted this request
        cursor.execute("SELECT * FROM Requests WHERE request_number = ?", (request_number,))  # re-read the request using the SAME connection/cursor
        columns = [description[0] for description in cursor.description]  # pull just the column names out
        row = cursor.fetchone()  # get the freshly-updated row (visible because it's the same connection/transaction)
        request_details = dict(zip(columns, row))  # turn it into a name -> value dictionary, same shape as load_request_details() returns
        create_event_from_request(cursor, request_details)  # copy the request's information into a brand new Events row

    connection.commit()  # commit() saves all our changes permanently
    connection.close()  # close the connection

    if new_status == "Accepted":  # give a more specific success message when an event was just created
        status_message.config(fg="green", text=f"Request #{request_number} accepted - Event created!")  # success message
    else:  # otherwise just confirm the status update
        status_message.config(fg="green", text=f"Request #{request_number} updated to '{new_status}'.")  # success message

    refresh_list()  # reload the listbox so it shows the updated status


update_button = tk.Button(details_frame, text="Update Status", command=update_status, bg="#4CAF50", fg="white")  # the main action button
update_button.pack(pady=10)  # place the button with spacing

refresh_list()  # populate the listbox for the first time when the window opens

window.mainloop()  # start the GUI event loop - keeps the window open and responsive until closed
