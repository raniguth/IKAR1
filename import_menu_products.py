# import_menu_products.py
# PURPOSE OF THIS FILE:
# This file reads your Excel file "products_for_the_menu.xlsx" and copies
# every product row into the MenuProducts table in the database. Run this
# ONCE, after running database_setup.py, and after placing the Excel file
# in the same folder as this script.
#
# If you update the Excel file later and want to re-import, first delete
# the existing rows from MenuProducts (e.g. in DB Browser), then run this
# file again - otherwise it will refuse to insert duplicates.

import pandas as pd  # import the library that reads Excel files into a table-like structure
import sqlite3  # import the library that lets Python talk to the SQLite database

EXCEL_FILE = "products_for_the_menu.xlsx"  # the name of the Excel file this script expects to find

spreadsheet = pd.read_excel(EXCEL_FILE)  # read the entire Excel file into a pandas DataFrame (a table in memory)

# the last row in your sheet is an "End" marker with a blank meal_type - we drop that row,
# since it isn't a real product and would fail our meal_type NOT NULL rule
spreadsheet = spreadsheet.dropna(subset=["meal_type"])  # dropna() removes any row where meal_type is blank/NaN

connection = sqlite3.connect("land_farmer.db")  # open a connection to our database file
cursor = connection.cursor()  # create a cursor to run commands with

cursor.execute("SELECT COUNT(*) FROM MenuProducts")  # check how many products already exist in the table
existing_count = cursor.fetchone()[0]  # get that count out of the result

if existing_count > 0:  # if there's already data in MenuProducts
    print(f"MenuProducts already has {existing_count} rows - skipping import to avoid duplicates.")  # explain why we're stopping
    print("If you want to re-import, delete the existing rows in DB Browser first, then run this script again.")  # tell them what to do instead
else:  # otherwise, the table is empty and safe to fill
    rows_inserted = 0  # a counter to keep track of how many rows we successfully insert
    for row in spreadsheet.itertuples(index=False):  # itertuples() lets us loop through the spreadsheet one row at a time
        # pandas represents a blank Excel cell as "NaN" (Not a Number) - we convert those to
        # Python's None, since that's what SQLite expects for an empty value
        meal_type_price = None if pd.isna(row.meal_type_price) else float(row.meal_type_price)  # convert NaN to None, otherwise keep the number
        addons_price = None if pd.isna(row.addons_price) else float(row.addons_price)  # same conversion for addons_price
        dish_description = None if pd.isna(row.dish_description) else str(row.dish_description)  # same conversion for dish_description
        menu_notes = None if pd.isna(row.menu_notes) else str(row.menu_notes)  # same conversion for menu_notes

        cursor.execute("""
            INSERT INTO MenuProducts (product_id, product_name, meal_type, category,
                                       dish_description, meal_type_price, addons_price, menu_notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (row.product_id, row.product_name, row.meal_type, row.category,
              dish_description, meal_type_price, addons_price, menu_notes))  # insert this product row
        rows_inserted += 1  # add 1 to our counter

    connection.commit()  # commit() saves all the inserted rows permanently
    print(f"Imported {rows_inserted} products into MenuProducts.")  # tell the user how many rows were added

connection.close()  # close the connection since we're done
