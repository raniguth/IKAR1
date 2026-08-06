# database_setup.py
# PURPOSE OF THIS FILE:
# This file creates the SQLite database for the "Land Farmer" restaurant
# event management system. It builds all the empty tables we designed,
# and fills in some starting data (opening hours, capacity, and the menu
# choice limits) so the app has something to work with immediately.
#
# You only need to RUN this file ONCE to create the database.
# If you run it again later, it will NOT erase your data - it safely
# skips creating tables that already exist.

import sqlite3  # import the built-in library that lets Python talk to SQLite databases

# connect() either opens the database file if it exists, or creates a new empty one if it doesn't
connection = sqlite3.connect("land_farmer.db")  # this creates/opens the file "land_farmer.db" in the same folder as this script

# a cursor is the tool we use to actually send commands (SQL statements) to the database
cursor = connection.cursor()  # create a cursor object linked to our connection

# ---------------------------------------------------------------------------
# TABLE 1: OpeningHours
# Stores which days the restaurant is open, and the open/close time for each day
# ---------------------------------------------------------------------------
cursor.execute("""
    CREATE TABLE IF NOT EXISTS OpeningHours (
        day_of_week TEXT PRIMARY KEY,
        open_time TEXT,
        close_time TEXT
    )
""")  # run the SQL command to create the OpeningHours table if it does not already exist

# ---------------------------------------------------------------------------
# TABLE 2: Settings
# Stores restaurant-wide settings, currently just the total guest capacity
# ---------------------------------------------------------------------------
cursor.execute("""
    CREATE TABLE IF NOT EXISTS Settings (
        setting_id INTEGER PRIMARY KEY AUTOINCREMENT,
        total_capacity INTEGER
    )
""")  # run the SQL command to create the Settings table if it does not already exist

# ---------------------------------------------------------------------------
# TABLE 3: Customers
# Stores the personal and contact details of each customer
# ---------------------------------------------------------------------------
cursor.execute("""
    CREATE TABLE IF NOT EXISTS Customers (
        customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT NOT NULL CHECK (length(first_name) BETWEEN 1 AND 20),
        last_name TEXT NOT NULL CHECK (length(last_name) BETWEEN 1 AND 20),
        id_number TEXT NOT NULL UNIQUE CHECK (id_number NOT GLOB '*[^0-9]*' AND length(id_number) BETWEEN 1 AND 10),
        company_name TEXT CHECK (company_name IS NULL OR length(company_name) <= 20),
        company_id_number TEXT CHECK (company_id_number IS NULL OR (company_id_number NOT GLOB '*[^0-9]*' AND length(company_id_number) <= 10)),
        phone TEXT NOT NULL CHECK (length(phone) BETWEEN 1 AND 10),
        email TEXT NOT NULL CHECK (length(email) <= 50 AND email LIKE '%@%')
    )
""")  # run the SQL command to create the Customers table if it does not already exist
# NOT NULL means this field can never be left empty
# UNIQUE on id_number means no two customers can share the same ID number
# BETWEEN 1 AND 20 means the text must be at least 1 character and at most 20 characters
# NOT GLOB '*[^0-9]*' means "does not contain any character that isn't a digit" - i.e. digits only
# company_name and company_id_number are optional (no NOT NULL), but if THEY are given a value,
# that value must still follow the length/digit rules above
# email LIKE '%@%' requires an @ symbol to appear somewhere in the text

# ---------------------------------------------------------------------------
# TABLE 4: ChoicesNumber
# Defines every valid (meal_type, category) combination, and how many
# products a client is allowed to pick from that category. This table is
# the "menu of the day" itself: every product in MenuProducts must belong
# to one of these combinations - that's enforced with a foreign key below.
# ---------------------------------------------------------------------------
cursor.execute("""
    CREATE TABLE IF NOT EXISTS ChoicesNumber (
        meal_type TEXT NOT NULL,
        category TEXT NOT NULL,
        can_choose INTEGER,
        PRIMARY KEY (meal_type, category)
    )
""")  # run the SQL command to create the ChoicesNumber table if it does not already exist
# PRIMARY KEY (meal_type, category) means each combination can only appear once,
# and it also creates the unique index that MenuProducts' foreign key (below) needs to point to
# can_choose has no NOT NULL - a blank value means "unlimited / not restricted" (e.g. "No Cat")

# ---------------------------------------------------------------------------
# TABLE 5: MenuProducts
# Every individual product the restaurant offers, imported from your Excel
# sheet. Each product belongs to one (meal_type, category) combination that
# must already exist in ChoicesNumber.
# ---------------------------------------------------------------------------
cursor.execute("""
    CREATE TABLE IF NOT EXISTS MenuProducts (
        product_id TEXT PRIMARY KEY,
        product_name TEXT NOT NULL,
        meal_type TEXT NOT NULL,
        category TEXT NOT NULL,
        dish_description TEXT,
        meal_type_price REAL,
        addons_price REAL,
        menu_notes TEXT CHECK (menu_notes IS NULL OR length(menu_notes) <= 200),
        FOREIGN KEY (meal_type, category) REFERENCES ChoicesNumber(meal_type, category)
    )
""")  # run the SQL command to create the MenuProducts table if it does not already exist
# product_id is the PRIMARY KEY here (not auto-generated) because your Excel sheet already
# provides its own IDs (M1, M2, M3...) - we use those exact values instead of making new ones
# meal_type_price is the flat per-guest price for choosing this meal (the SAME value repeats
# on every regular product row for that meal type - e.g. every Breakfast row shows 120)
# addons_price is only filled in for add-on products (meal_type_price is blank for those, and
# vice versa) - a product is either part of the base meal, or a separate priced add-on, not both

# ---------------------------------------------------------------------------
# TABLE 6: Requests
# Stores every initial inquiry, before it becomes a confirmed event
# ---------------------------------------------------------------------------
cursor.execute("""
    CREATE TABLE IF NOT EXISTS Requests (
        request_number INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        request_date TEXT NOT NULL,
        requested_event_date TEXT NOT NULL,
        requested_start_time TEXT NOT NULL,
        requested_end_time TEXT NOT NULL,
        num_guests INTEGER NOT NULL CHECK (num_guests > 0),
        event_type TEXT CHECK (event_type IS NULL OR length(event_type) <= 20),
        dietary_restrictions TEXT CHECK (dietary_restrictions IS NULL OR length(dietary_restrictions) <= 100),
        special_requests TEXT CHECK (special_requests IS NULL OR length(special_requests) <= 200),
        notes TEXT CHECK (notes IS NULL OR length(notes) <= 200),
        status TEXT NOT NULL DEFAULT 'New Inquiry' CHECK (status IN ('New Inquiry', 'Quoted', 'Accepted', 'Declined')),
        accepted_time TEXT,
        meal_option TEXT CHECK (meal_option IS NULL OR meal_option IN ('Breakfast', 'Lunch')),
        quoted_total_price REAL,
        FOREIGN KEY (customer_id) REFERENCES Customers(customer_id)
    )
""")  # run the SQL command to create the Requests table if it does not already exist
# CHECK (num_guests > 0) rejects any attempt to save zero or negative guests
# event_type is optional - it can be left empty
# dietary_restrictions/special_requests/notes each have a maximum length, but can still be empty
# status has a DEFAULT, so if you don't specify one, it automatically becomes 'New Inquiry'
# status also has a CHECK that only allows exactly these 4 words - any other text is rejected
# accepted_time starts empty, and gets filled in with the exact date+time the client clicks
# "I confirm the price and the order" in Build Your Menu (format: YYYY-MM-DD HH:MM:SS)
# meal_option (Breakfast/Lunch) and quoted_total_price start empty, and get filled in by the
# "Build Your Menu" screen once the client chooses their meal option and products
# NOTE: the event date/time/guest-capacity rules involve OTHER tables (OpeningHours, Settings),
# and SQLite's CHECK constraints are NOT allowed to reference other tables - so those rules are
# enforced further down using TRIGGERS instead, which CAN look at other tables

# ---------------------------------------------------------------------------
# TRIGGERS: cross-table validation rules for Requests
# A TRIGGER is a piece of SQL that runs automatically every time a row is
# inserted or updated - even if that insert/update happens directly inside
# DB Browser, not through our Python app. RAISE(ABORT, message) cancels the
# insert/update entirely and shows that message, exactly like a CHECK does,
# but a TRIGGER is allowed to look at OTHER tables (OpeningHours, Settings),
# which a plain CHECK constraint is not allowed to do.
#
# We build the same set of rules as a reusable piece of text, then create it
# twice - once for INSERT and once for UPDATE - so both new rows and edits
# to existing rows are equally protected.
# ---------------------------------------------------------------------------

# this CASE expression converts a date into its weekday NAME ("Sunday", "Monday", etc.)
# so we can look up the matching row in OpeningHours (which stores day names, not numbers)
weekday_name_case = """CASE CAST(strftime('%w', NEW.requested_event_date) AS INTEGER)
        WHEN 0 THEN 'Sunday' WHEN 1 THEN 'Monday' WHEN 2 THEN 'Tuesday'
        WHEN 3 THEN 'Wednesday' WHEN 4 THEN 'Thursday' WHEN 5 THEN 'Friday'
        WHEN 6 THEN 'Saturday' END"""  # strftime('%w', date) returns 0=Sunday through 6=Saturday

# this is the full set of validation rules, written once and reused for both triggers below
trigger_rules_sql = f"""
    -- Rule: request_date must be a real, correctly-formatted YYYY-MM-DD date
    SELECT RAISE(ABORT, 'request_date must be a valid YYYY-MM-DD date')
    WHERE NEW.request_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
       OR julianday(NEW.request_date) IS NULL;

    -- Rule: requested_event_date must be a real, correctly-formatted YYYY-MM-DD date
    SELECT RAISE(ABORT, 'requested_event_date must be a valid YYYY-MM-DD date')
    WHERE NEW.requested_event_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
       OR julianday(NEW.requested_event_date) IS NULL;

    -- Rule: the event date must be at least one full day after the request date
    SELECT RAISE(ABORT, 'Event date must be at least one day after the request date')
    WHERE date(NEW.requested_event_date) <= date(NEW.request_date);

    -- Rule: start time must be a real, correctly-formatted HH:MM time
    SELECT RAISE(ABORT, 'requested_start_time must be a valid HH:MM time')
    WHERE NEW.requested_start_time NOT GLOB '[0-9][0-9]:[0-9][0-9]'
       OR CAST(substr(NEW.requested_start_time, 1, 2) AS INTEGER) > 23
       OR CAST(substr(NEW.requested_start_time, 4, 2) AS INTEGER) > 59;

    -- Rule: end time must be a real, correctly-formatted HH:MM time
    SELECT RAISE(ABORT, 'requested_end_time must be a valid HH:MM time')
    WHERE NEW.requested_end_time NOT GLOB '[0-9][0-9]:[0-9][0-9]'
       OR CAST(substr(NEW.requested_end_time, 1, 2) AS INTEGER) > 23
       OR CAST(substr(NEW.requested_end_time, 4, 2) AS INTEGER) > 59;

    -- Rule: the restaurant must actually be open on the event's day of the week
    SELECT RAISE(ABORT, 'Restaurant is closed on this day')
    WHERE (SELECT open_time FROM OpeningHours WHERE day_of_week = {weekday_name_case}) IS NULL;

    -- Rule: start time must be after opening, and at least one hour before closing
    SELECT RAISE(ABORT, 'Start time must be within opening hours (and at least 1 hour before closing)')
    WHERE NEW.requested_start_time <= (SELECT open_time FROM OpeningHours WHERE day_of_week = {weekday_name_case})
       OR NEW.requested_start_time > (SELECT time(close_time, '-1 hours') FROM OpeningHours WHERE day_of_week = {weekday_name_case});

    -- Rule: end time must be after opening, and at least one hour before closing
    SELECT RAISE(ABORT, 'End time must be within opening hours (and at least 1 hour before closing)')
    WHERE NEW.requested_end_time <= (SELECT open_time FROM OpeningHours WHERE day_of_week = {weekday_name_case})
       OR NEW.requested_end_time > (SELECT time(close_time, '-1 hours') FROM OpeningHours WHERE day_of_week = {weekday_name_case});

    -- Rule: number of guests cannot exceed the restaurant's total capacity
    SELECT RAISE(ABORT, 'Number of guests exceeds restaurant capacity')
    WHERE NEW.num_guests > (SELECT total_capacity FROM Settings LIMIT 1);
"""  # this whole block of rules gets reused below for both the INSERT and UPDATE triggers

cursor.execute(f"""
    CREATE TRIGGER IF NOT EXISTS trg_validate_request_insert
    BEFORE INSERT ON Requests
    FOR EACH ROW
    BEGIN
        {trigger_rules_sql}
    END;
""")  # create the trigger that checks these rules every time a NEW request is inserted

cursor.execute(f"""
    CREATE TRIGGER IF NOT EXISTS trg_validate_request_update
    BEFORE UPDATE ON Requests
    FOR EACH ROW
    BEGIN
        {trigger_rules_sql}
    END;
""")  # create the trigger that checks these SAME rules every time an existing request is edited

# ---------------------------------------------------------------------------
# TABLE 7: RequestProducts
# Links a Request to every MenuProducts item the client selected while
# building their menu (one row per chosen product)
# ---------------------------------------------------------------------------
cursor.execute("""
    CREATE TABLE IF NOT EXISTS RequestProducts (
        request_number INTEGER NOT NULL,
        product_id TEXT NOT NULL,
        PRIMARY KEY (request_number, product_id),
        FOREIGN KEY (request_number) REFERENCES Requests(request_number),
        FOREIGN KEY (product_id) REFERENCES MenuProducts(product_id)
    )
""")  # run the SQL command to create the RequestProducts table if it does not already exist
# PRIMARY KEY (request_number, product_id) means the SAME product can never be added
# twice to the same request - this enforces "each product only once" at the database level

# ---------------------------------------------------------------------------
# TABLE 8: Events
# Stores confirmed events, created only after a Request is Accepted
# ---------------------------------------------------------------------------
cursor.execute("""
    CREATE TABLE IF NOT EXISTS Events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_number INTEGER NOT NULL,
        customer_id INTEGER NOT NULL,
        event_date TEXT NOT NULL,
        event_start_time TEXT NOT NULL,
        event_end_time TEXT NOT NULL,
        num_guests INTEGER NOT NULL CHECK (num_guests > 0),
        event_type TEXT,
        dietary_restrictions TEXT,
        special_requests TEXT,
        notes TEXT,
        meal_option TEXT CHECK (meal_option IS NULL OR meal_option IN ('Breakfast', 'Lunch')),
        total_price REAL NOT NULL CHECK (total_price >= 0),
        deposit_paid INTEGER CHECK (deposit_paid IS NULL OR deposit_paid >= 0),
        status TEXT NOT NULL DEFAULT 'Confirmed' CHECK (status IN ('Confirmed', 'In Preparation', 'Completed', 'Feedback Received')),
        FOREIGN KEY (request_number) REFERENCES Requests(request_number),
        FOREIGN KEY (customer_id) REFERENCES Customers(customer_id)
    )
""")  # run the SQL command to create the Events table if it does not already exist
# deposit_paid holds the ACTUAL AMOUNT paid so far (a whole number), not a yes/no flag -
# it starts empty (NULL) and gets filled in later from the Dashboard's UPDATE screen,
# either by "Confirm Payment" (sets it to the full total_price) or "Update Price" (a custom amount)
# Almost every other field here is required because our Python code will
# copy it automatically from the matching Request - you will never type it by hand

# ---------------------------------------------------------------------------
# TABLE 9: EventProducts
# Links a confirmed Event to every product that ended up in the final menu
# (copied over from RequestProducts at the moment the request is Accepted)
# ---------------------------------------------------------------------------
cursor.execute("""
    CREATE TABLE IF NOT EXISTS EventProducts (
        event_id INTEGER NOT NULL,
        product_id TEXT NOT NULL,
        PRIMARY KEY (event_id, product_id),
        FOREIGN KEY (event_id) REFERENCES Events(event_id),
        FOREIGN KEY (product_id) REFERENCES MenuProducts(product_id)
    )
""")  # run the SQL command to create the EventProducts table if it does not already exist

# ---------------------------------------------------------------------------
# TABLE 10: Feedback
# Stores the customer's feedback after the event is completed
# ---------------------------------------------------------------------------
cursor.execute("""
    CREATE TABLE IF NOT EXISTS Feedback (
        feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL,
        overall_rating INTEGER CHECK (overall_rating IS NULL OR overall_rating BETWEEN 1 AND 5),
        food_rating INTEGER CHECK (food_rating IS NULL OR food_rating BETWEEN 1 AND 5),
        service_rating INTEGER CHECK (service_rating IS NULL OR service_rating BETWEEN 1 AND 5),
        would_recommend INTEGER CHECK (would_recommend IS NULL OR would_recommend BETWEEN 1 AND 5),
        comments TEXT CHECK (comments IS NULL OR length(comments) <= 20),
        feedback_date TEXT,
        FOREIGN KEY (event_id) REFERENCES Events(event_id)
    )
""")  # run the SQL command to create the Feedback table if it does not already exist
# event_id is required and will always be auto-filled by the app - never typed by hand
# overall_rating, food_rating, service_rating, and would_recommend are all OPTIONAL,
# but IF a value is given for any of them, it must be between 1 and 5
# comments is optional too, but limited to 20 characters if given

# ---------------------------------------------------------------------------
# STARTING DATA
# We only insert this data if the tables are currently empty, so running
# this file again later will not create duplicate rows
# ---------------------------------------------------------------------------

cursor.execute("SELECT COUNT(*) FROM Settings")  # ask the database how many rows already exist in Settings
settings_count = cursor.fetchone()[0]  # fetchone() gets that single result, and [0] pulls the number out of it

if settings_count == 0:  # only insert default settings if the table is currently empty
    cursor.execute("INSERT INTO Settings (total_capacity) VALUES (150)")  # insert the default restaurant capacity of 150 guests

cursor.execute("SELECT COUNT(*) FROM OpeningHours")  # ask the database how many rows already exist in OpeningHours
hours_count = cursor.fetchone()[0]  # get that count out of the result

if hours_count == 0:  # only insert default opening hours if the table is currently empty
    opening_hours_data = [  # build a list of tuples, one tuple per day, matching the table's columns
        ("Sunday", "08:00", "22:00"),
        ("Monday", "08:00", "22:00"),
        ("Tuesday", "08:00", "22:00"),
        ("Wednesday", "08:00", "22:00"),
        ("Thursday", "08:00", "22:00"),
        ("Friday", "08:00", "14:00"),
        ("Saturday", None, None),  # None means "closed" - no opening hours on Saturday
    ]
    cursor.executemany(  # executemany() runs the same INSERT command once for every tuple in the list
        "INSERT INTO OpeningHours (day_of_week, open_time, close_time) VALUES (?, ?, ?)",
        opening_hours_data
    )  # the ? symbols are placeholders that get safely filled in with each tuple's values

cursor.execute("SELECT COUNT(*) FROM ChoicesNumber")  # ask the database how many rows already exist in ChoicesNumber
choices_count = cursor.fetchone()[0]  # get that count out of the result

if choices_count == 0:  # only insert the choice limits if the table is currently empty
    choices_data = [  # this is exactly the table you provided, EXCLUDING the "END / End" row,
        # which was a spreadsheet "end of table" marker, not a real menu category
        ("Breakfast", "Breakfast Starters", 3),
        ("Breakfast", "Breakfast Main", 2),
        ("Breakfast", "Breakfast Salads", 2),
        ("Breakfast", "Breakfast Desserts", 1),
        ("Breakfast", "Breakfast Hot Drinks", 1),
        ("Breakfast", "Breakfast Cold Drinks", 1),
        ("Lunch", "Lunch Starters", 3),
        ("Lunch", "Lunch Main", 2),
        ("Lunch", "Lunch Salads", 2),
        ("Lunch", "Lunch Desserts", 1),
        ("Lunch", "Lunch Hot Drinks", 1),
        ("Lunch", "Lunch Cold Drinks", 1),
        ("Any Meal", "addons", 5),
        ("Any Meal", "No Cat", None),  # None (blank) means "no limit" - this is the "Nothing to Add" option
    ]
    cursor.executemany(  # run the same INSERT command once per row
        "INSERT INTO ChoicesNumber (meal_type, category, can_choose) VALUES (?, ?, ?)",
        choices_data
    )  # fill in the ? placeholders with each row's values

# ---------------------------------------------------------------------------
# SAVE AND CLOSE
# ---------------------------------------------------------------------------
connection.commit()  # commit() saves all the changes we made permanently to the database file
connection.close()  # close() properly closes the connection to the database file

print("Database setup complete! The file land_farmer.db has been created/updated.")  # print a friendly confirmation message so you know it worked
print("NOTE: MenuProducts is still empty - run import_menu_products.py next to load your Excel menu.")  # remind about the next step
