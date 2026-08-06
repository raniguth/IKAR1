# Land Farmer (Ikar HaAretz) - Event Management System

A desktop application for managing private event bookings at the Land Farmer
restaurant, from the first customer inquiry through menu selection, quoting,
booking confirmation, payment tracking, and post-event feedback.

Built in Python using `tkinter` for the interface and a local `SQLite`
database for storage, as a course project.

## What's included

| File | Purpose |
|---|---|
| `database_setup.py` | Creates the SQLite database and all tables (run this first) |
| `import_menu_products.py` | Imports the restaurant's menu from an Excel file |
| `new_request_screen.py` | The "New Event Request" intake form (the main screen to run) |
| `date_picker.py` | The pop-up monthly calendar used for choosing an event date |
| `ikalendar.py` | The visual weekly availability calendar |
| `admin_calendar.py` | A standalone launcher for the admin (past-browsing) calendar |
| `build_your_menu.py` | The menu-building and quoting screen |
| `update_request_status.py` | Screen for reviewing/accepting/declining requests |
| `dashboard.py` | The manager's home screen: weekly summary, income chart, and admin tools |

## Setup

1. Install Python 3.12 or later.
2. Install the extra packages this project needs:
   ```
   pip install -r requirements.txt
   ```
3. Create the database (only needs to be done once):
   ```
   python database_setup.py
   ```
4. Import the menu (make sure `products_for_the_menu.xlsx` is in this folder first):
   ```
   python import_menu_products.py
   ```
5. Run the app. For day-to-day use, start with:
   ```
   python dashboard.py
   ```
   or, to take a new customer inquiry directly:
   ```
   python new_request_screen.py
   ```

## Note on data privacy

The database file (`land_farmer.db`) is intentionally excluded from this
repository (see `.gitignore`) since it will contain real customer names,
phone numbers, and emails once used. Each setup starts with a fresh, empty
database.
