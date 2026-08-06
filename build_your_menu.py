# build_your_menu.py
# PURPOSE OF THIS FILE:
# This file shows the "Build Your Menu" window. The client (or the admin,
# speaking with the client on the phone) first picks Breakfast or Lunch,
# then picks specific dishes/add-ons within the allowed limits per category,
# gets an instant price quote, and either confirms it (which accepts the
# request and creates the Event automatically) or starts over.

import tkinter as tk  # import the GUI library, nicknamed "tk"
from tkinter import messagebox  # import the pop-up message box part of tkinter
import sqlite3  # import the library that lets Python talk to the SQLite database
import datetime  # import the library that helps us work with dates and times
import webbrowser  # import the library that lets Python open a page in the computer's web browser


def get_connection():
    return sqlite3.connect("land_farmer.db")  # open (and return) a fresh connection to our database file


# ---------------------------------------------------------------------------
# DATABASE HELPER FUNCTIONS
# ---------------------------------------------------------------------------

def get_meal_type_price(cursor, meal_option):
    # every product of a given meal_type shares the SAME meal_type_price, so we only need one value
    cursor.execute("SELECT meal_type_price FROM MenuProducts WHERE meal_type = ? AND meal_type_price IS NOT NULL LIMIT 1", (meal_option,))
    row = cursor.fetchone()  # fetchone() gets the single matching row, or None if somehow not found
    return row[0] if row is not None else 0.0  # return that price, or 0.0 as a safe fallback


def get_categories_for_meal_option(cursor, meal_option):
    # returns every (category, can_choose) pair relevant to this meal option - the chosen meal type PLUS "Any Meal"
    cursor.execute("""
        SELECT category, can_choose FROM ChoicesNumber
        WHERE meal_type = ? OR meal_type = 'Any Meal'
        ORDER BY (meal_type = 'Any Meal'), rowid
    """, (meal_option,))  # ORDER BY puts the meal-specific categories first, "Any Meal" categories last
    return cursor.fetchall()  # return every matching row


def get_products_for_category(cursor, meal_option, category):
    # returns every product belonging to this category, for either the chosen meal type or "Any Meal"
    cursor.execute("""
        SELECT product_id, product_name, dish_description, addons_price
        FROM MenuProducts
        WHERE category = ? AND (meal_type = ? OR meal_type = 'Any Meal')
        ORDER BY product_id
    """, (category, meal_option))
    return cursor.fetchall()  # return every matching product row


def save_request_products(cursor, request_number, product_ids):
    # this function replaces whatever products were previously saved for this request with the current selection
    cursor.execute("DELETE FROM RequestProducts WHERE request_number = ?", (request_number,))  # clear any old selections first
    for product_id in product_ids:  # loop through every currently selected product
        cursor.execute("INSERT INTO RequestProducts (request_number, product_id) VALUES (?, ?)", (request_number, product_id))  # save it


def accept_request_and_create_event(cursor, request_number, meal_option, quoted_total_price):
    # this function finalizes everything: marks the Request Accepted, and creates the matching Event
    accepted_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # capture the exact moment of confirmation
    cursor.execute(
        "UPDATE Requests SET meal_option = ?, quoted_total_price = ?, status = 'Accepted', accepted_time = ? WHERE request_number = ?",
        (meal_option, quoted_total_price, accepted_time, request_number)
    )  # save the final meal option, price, Accepted status, and the exact confirmation time

    cursor.execute("SELECT * FROM Requests WHERE request_number = ?", (request_number,))  # re-read the request using the SAME connection
    columns = [description[0] for description in cursor.description]  # pull the column names out
    request_row = dict(zip(columns, cursor.fetchone()))  # turn the row into a name -> value dictionary

    cursor.execute("""
        INSERT INTO Events (request_number, customer_id, event_date, event_start_time, event_end_time,
                             num_guests, event_type, dietary_restrictions, special_requests, notes,
                             meal_option, total_price)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        request_row["request_number"], request_row["customer_id"], request_row["requested_event_date"],
        request_row["requested_start_time"], request_row["requested_end_time"], request_row["num_guests"],
        request_row["event_type"], request_row["dietary_restrictions"], request_row["special_requests"],
        request_row["notes"], request_row["meal_option"], request_row["quoted_total_price"]
    ))  # create the new Event row, copying the request's information (status defaults to 'Confirmed')
    event_id = cursor.lastrowid  # lastrowid gives us the event_id that SQLite just auto-generated

    cursor.execute("SELECT product_id FROM RequestProducts WHERE request_number = ?", (request_number,))  # get every chosen product
    for (product_id,) in cursor.fetchall():  # loop through each one (each row is a 1-item tuple, hence the comma)
        cursor.execute("INSERT INTO EventProducts (event_id, product_id) VALUES (?, ?)", (event_id, product_id))  # copy it onto the event


# ---------------------------------------------------------------------------
# GUI: THE MENU BUILDER WINDOW
# ---------------------------------------------------------------------------

def open_menu_builder(parent, request_number, on_complete=None):
    # this is the main function other files call to open the Build Your Menu window
    # request_number: the already-saved Request this menu belongs to
    # on_complete: an optional function to call once the client confirms their order (e.g. to clear the form)

    builder_window = tk.Toplevel(parent)  # Toplevel creates a new pop-up window on top of the parent window
    builder_window.title("Build Your Menu")  # set the pop-up window's title bar text
    builder_window.geometry("700x650")  # set the starting size of the pop-up window

    state = {"meal_option": None, "selections": {}}  # a dictionary to remember the chosen meal option and product checkboxes across functions

    content_frame = tk.Frame(builder_window)  # a frame that holds whichever "step" is currently showing
    content_frame.pack(fill="both", expand=True)  # place it, filling the whole window

    def clear_content():
        for widget in content_frame.winfo_children():  # loop through every widget currently inside content_frame
            widget.destroy()  # remove it, so we can draw the next step fresh

    # -----------------------------------------------------------------
    # STEP 1: choose Breakfast or Lunch
    # -----------------------------------------------------------------
    def show_step_1():
        clear_content()  # wipe whatever was showing before
        state["meal_option"] = None  # reset the chosen meal option
        state["selections"] = {}  # reset any previously chosen products

        tk.Label(content_frame, text="Build Your Menu", font=("Arial", 16, "bold")).pack(pady=20)  # heading
        tk.Label(content_frame, text="First, choose your meal option:", font=("Arial", 11)).pack(pady=10)  # instructions

        button_row = tk.Frame(content_frame)  # a frame to hold the two option buttons side by side
        button_row.pack(pady=20)  # place it with spacing
        tk.Button(button_row, text="Breakfast", font=("Arial", 12), width=15, height=2, bg="#2196F3", fg="white",
                  command=lambda: show_step_2("Breakfast")).grid(row=0, column=0, padx=15)  # Breakfast button
        tk.Button(button_row, text="Lunch", font=("Arial", 12), width=15, height=2, bg="#2196F3", fg="white",
                  command=lambda: show_step_2("Lunch")).grid(row=0, column=1, padx=15)  # Lunch button

        tk.Button(content_frame, text="Exit the Reservation", command=builder_window.destroy).pack(pady=30)  # lets the client leave at any time

    # -----------------------------------------------------------------
    # STEP 2: choose products within each category's limit
    # -----------------------------------------------------------------
    def show_step_2(meal_option):
        clear_content()  # wipe step 1
        state["meal_option"] = meal_option  # remember which meal option was chosen
        state["selections"] = {}  # start with nothing selected

        tk.Label(content_frame, text=f"Building your {meal_option} menu", font=("Arial", 14, "bold")).pack(pady=10)  # heading

        tk.Button(content_frame, text="Show the dishes", font=("Arial", 11, "bold"), bg="#FF9800", fg="white",
                  command=lambda: webbrowser.open("http://www.ikar-haaretz.com")).pack(pady=(0, 10))  # opens the restaurant's menu website in a browser tab

        # a scrollable area, since there may be many categories/products to show
        canvas = tk.Canvas(content_frame)  # a scrollable drawing surface
        scrollbar = tk.Scrollbar(content_frame, orient="vertical", command=canvas.yview)  # a vertical scrollbar linked to it
        scroll_frame = tk.Frame(canvas)  # the frame that will actually hold all the categories/products
        scroll_frame.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))  # keep scroll area updated
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")  # place scroll_frame inside the canvas
        canvas.configure(yscrollcommand=scrollbar.set)  # connect the canvas's vertical position to the scrollbar
        canvas.pack(side="left", fill="both", expand=True, padx=10)  # place the canvas, filling remaining space
        scrollbar.pack(side="right", fill="y")  # place the scrollbar along the right edge

        def on_mousewheel(event):
            canvas.yview_scroll(-1 * (event.delta // 120), "units")  # scroll the canvas up/down with the mouse wheel
        canvas.bind_all("<MouseWheel>", on_mousewheel)  # activate mouse wheel scrolling over this window

        connection = get_connection()  # open a connection
        cursor = connection.cursor()  # create a cursor
        categories = get_categories_for_meal_option(cursor, meal_option)  # get every relevant category and its limit

        category_vars = {}  # will hold category -> list of (product_id, IntVar) pairs, so we can count selections per category

        def make_limit_checker(category, limit):
            # this builds a small function that runs whenever ANY checkbox in this category is clicked
            def check_limit():
                if limit is None:  # None means "no limit" - nothing to enforce
                    return  # do nothing
                checked_count = sum(var.get() for product_id, var in category_vars[category])  # count how many boxes are checked in this category
                if checked_count > limit:  # if the client just went over the allowed limit
                    messagebox.showwarning("Limit Reached", f"You can only choose up to {limit} item(s) from '{category}'.")  # explain why
                    # find the checkbox that was JUST turned on, and turn it back off, since it pushed us over the limit
                    for product_id, var in category_vars[category]:  # loop through this category's checkboxes
                        if var.get() == 1:  # find one that's currently checked
                            var.set(0)  # un-check it
                            break  # only undo ONE click, then stop
            return check_limit  # give back this ready-to-use function

        for category, can_choose in categories:  # loop through every relevant category
            products = get_products_for_category(cursor, meal_option, category)  # get this category's products
            if not products:  # skip categories that happen to have no products (shouldn't normally occur)
                continue  # move to the next category

            limit_text = f"(choose up to {can_choose})" if can_choose is not None else "(no limit)"  # build a readable limit description
            section = tk.LabelFrame(scroll_frame, text=f"{category} {limit_text}", font=("Arial", 10, "bold"))  # a titled box for this category
            section.pack(fill="x", padx=10, pady=8, anchor="w")  # place it, stretching to the full width

            category_vars[category] = []  # start this category's list of checkboxes empty

            for product_id, product_name, dish_description, addons_price in products:  # loop through every product in this category
                var = tk.IntVar(builder_window, value=0)  # a variable to track whether this product's checkbox is checked (0 or 1)
                price_text = f" (+₪{addons_price:.2f} per guest)" if addons_price not in (None, 0) else ""  # show a price tag only for priced add-ons
                label_text = f"{product_name}{price_text}" + (f" - {dish_description}" if dish_description else "")  # build the full checkbox label
                checkbox = tk.Checkbutton(section, text=label_text, variable=var,
                                           command=make_limit_checker(category, can_choose))  # create the checkbox, wired to enforce the limit
                checkbox.pack(anchor="w", padx=10, pady=2)  # place the checkbox
                category_vars[category].append((product_id, var))  # remember this checkbox for counting/reading later
                state["selections"][product_id] = var  # also remember it globally, so we can read every selection when quoting

        connection.close()  # close the connection, we've loaded everything we need

        # bottom buttons (outside the scrollable area, so they're always visible)
        bottom_frame = tk.Frame(content_frame)  # a frame to hold the action buttons
        bottom_frame.pack(pady=15)  # place it below the scrollable area
        tk.Button(bottom_frame, text="Get a Quote ₪", font=("Arial", 11), bg="#4CAF50", fg="white",
                  command=lambda: show_quote(meal_option)).grid(row=0, column=0, padx=10)  # the quote button
        tk.Button(bottom_frame, text="Exit the Reservation", command=builder_window.destroy).grid(row=0, column=1, padx=10)  # the exit button

    # -----------------------------------------------------------------
    # QUOTE: calculate and display the price
    # -----------------------------------------------------------------
    def show_quote(meal_option):
        connection = get_connection()  # open a connection
        cursor = connection.cursor()  # create a cursor

        cursor.execute("SELECT num_guests FROM Requests WHERE request_number = ?", (request_number,))  # get this request's guest count
        num_guests = cursor.fetchone()[0]  # extract the number

        meal_price = get_meal_type_price(cursor, meal_option)  # get the ONE flat price for this meal option

        selected_product_ids = [product_id for product_id, var in state["selections"].items() if var.get() == 1]  # every currently checked product

        addons_total = 0.0  # start the add-ons total at zero
        chosen_items_text = []  # a list of readable lines describing what was chosen, for the itemized list
        for product_id in selected_product_ids:  # loop through every selected product
            cursor.execute("SELECT product_name, category, addons_price FROM MenuProducts WHERE product_id = ?", (product_id,))  # look it up
            product_name, category, addons_price = cursor.fetchone()  # unpack its details
            if addons_price:  # if this product has a real (non-zero, non-None) add-on price
                addons_total += addons_price  # add it to our running add-ons total
            chosen_items_text.append(f"{category}: {product_name}")  # add a readable line for the itemized list

        connection.close()  # close the connection

        total_price = (meal_price + addons_total) * num_guests  # apply your exact formula: (meal price + add-ons) * guests

        quote_window = tk.Toplevel(builder_window)  # a new pop-up window to show the quote
        quote_window.title("Your Quote")  # set its title bar text
        quote_window.geometry("450x500")  # set its size

        tk.Label(quote_window, text="Your Quote", font=("Arial", 16, "bold")).pack(pady=15)  # heading
        tk.Label(quote_window, text=f"₪{total_price:,.2f}", font=("Arial", 20, "bold"), fg="#2E7D32").pack(pady=5)  # the big price display
        tk.Label(quote_window, text=f"({meal_price:.2f} meal + {addons_total:.2f} add-ons) × {num_guests} guests",
                 font=("Arial", 9), fg="gray").pack(pady=(0, 15))  # a small breakdown of how we got that number

        tk.Label(quote_window, text="Your selections:", font=("Arial", 11, "bold")).pack(anchor="w", padx=20)  # itemized list heading
        items_box = tk.Listbox(quote_window, width=50, height=12)  # a list box to show every chosen item
        items_box.pack(padx=20, pady=5)  # place it with spacing
        if chosen_items_text:  # if anything was actually selected
            for line in chosen_items_text:  # loop through every chosen item's description
                items_box.insert(tk.END, line)  # add it to the list box
        else:  # if nothing was selected at all
            items_box.insert(tk.END, "(no items selected)")  # show a placeholder message

        def confirm_order():
            connection2 = get_connection()  # open a fresh connection for saving
            cursor2 = connection2.cursor()  # create a cursor
            save_request_products(cursor2, request_number, selected_product_ids)  # save the final chosen products
            accept_request_and_create_event(cursor2, request_number, meal_option, total_price)  # accept the request and create the Event
            connection2.commit()  # save everything permanently
            connection2.close()  # close the connection

            quote_window.destroy()  # close the quote window
            confirmation_window = tk.Toplevel(builder_window)  # a small final window to confirm everything worked
            confirmation_window.title("Confirmed")  # set its title bar text
            confirmation_window.geometry("300x150")  # set its size
            tk.Label(confirmation_window, text="Great, see you soon!", font=("Arial", 14, "bold")).pack(pady=30)  # the confirmation message

            def finish_and_close():
                # runs whether the client clicks "Close" OR closes the window with the X button -
                # either way we just close everything and clear the New Request form, nothing new opens
                confirmation_window.destroy()  # close this small confirmation window
                builder_window.destroy()  # close the whole Build Your Menu window
                if on_complete is not None:  # if the caller gave us something to run afterward (e.g. clearing the New Request form)
                    on_complete()  # run it

            tk.Button(confirmation_window, text="Close", command=finish_and_close).pack()  # the Close button
            confirmation_window.protocol("WM_DELETE_WINDOW", finish_and_close)  # also run the same cleanup if closed via the window's X button

        def start_new_quote():
            quote_window.destroy()  # close the quote window
            show_step_1()  # go all the way back to choosing Breakfast/Lunch again

        button_row = tk.Frame(quote_window)  # a frame to hold the two decision buttons
        cancellation_notice = tk.Label(
            quote_window,
            text="Bookings canceled by the client fewer than 3 days before the event\nare subject to a ₪1,000 cancellation fee.",
            font=("Arial", 9), fg="#B71C1C", justify="center"
        )  # the cancellation policy notice, shown right above the confirm button
        cancellation_notice.pack(pady=(10, 5))  # place it just before the button row below
        button_row.pack(pady=15)  # place the button row with spacing
        tk.Button(button_row, text="I confirm the price and the order", bg="#4CAF50", fg="white",
                  command=confirm_order).grid(row=0, column=0, padx=5)  # the confirm button
        tk.Button(button_row, text="Please start a new Quote", command=start_new_quote).grid(row=0, column=1, padx=5)  # the restart button

    show_step_1()  # draw the first step when the window first opens
