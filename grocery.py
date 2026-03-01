from flask import Blueprint, render_template, request, redirect, url_for
from pymongo import MongoClient
import os
import datetime

'''
This module defines the grocery blueprint for the Flask application. It handles routes related to the grocery list, including displaying the current list, adding items, saving weekly history, and viewing past grocery lists.
'''
client = MongoClient(os.getenv("MONGO_URI"))
grocery_bp = Blueprint('grocery', __name__, template_folder='groceryDisplay')
db = client["grocerydb"]


current_week = db["current_list"]
grocery_history = db["grocery_list_test"]

#grocery list page - displays current grocery list and allows adding items
@grocery_bp.route("/grocery-list", methods=["GET", "POST"])
def grocery_list():
    """
    Route for grocery list page - displays current grocery list and allows adding items.
    """
    if request.method == "POST":
        # Handle adding new item to grocery list
        name = request.form.get("food-name")
        amount = request.form.get("amount")
        if name and amount:
            current_week.insert_one({
                "name": name,
                "amount": amount,
                "date_added": datetime.datetime.utcnow()
            })
            return redirect(url_for("grocery.grocery_list"))

    #  GET request - display grocery list
    items = list(current_week.find())
    return render_template("grocery-list.html", items=items)

@grocery_bp.route("/save-week")
def save_week():

    items = list(current_week.find())
    if items:
        grocery_history.insert_one({
            "week": datetime.datetime.utcnow(),
            "items": items
        })
        #if copy current items to history, then clear current week as week is over
        current_week.delete_many({})
    return redirect(url_for("grocery.grocery_history_page"))

@grocery_bp.route("/grocery-history")
def grocery_history_page():
    history = list(grocery_history.find().sort("week", -1))  # Sort by week in descending order
    return render_template("grocery-history.html", history=history)

from flask import send_from_directory

