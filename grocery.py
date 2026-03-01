from flask import Blueprint, render_template, request, redirect, url_for
from pymongo import MongoClient
import os
import datetime


client = MongoClient(os.getenv("MONGO_URI"))

db1 = client["groceryfood"] #food that groceryList will pull from to add to the list, and also to save the history of what was added to the list each week.
db2 = client["groceryList"] #current grocery list

grocery_bp = Blueprint('grocery', __name__, template_folder='groceryDisplay')

current_list = []
# grocery_history = [
#     {
#         "week": "10/01/2024",
#         "items": [
#             {"name": "Milk", "date_added": "10/02/2024", "amount": "1 gallon"},
#             {"name": "Eggs", "date_added": "10/03/2024", "amount": "1 dozen"},
#             {"name": "Broccoli", "date_added": "10/03/2024", "amount": "3 heads"},
#         ]
#     },
#     {
#         "week": "10/08/2024",
#         "items": [
#             {"name": "Chicken Breast", "date_added": "10/09/2024", "amount": "2 lbs"},
#             {"name": "Rice", "date_added": "10/09/2024", "amount": "5 lbs"},
#             {"name": "Spinach", "date_added": "10/10/2024", "amount": "2 bags"},
#         ]
#     },
#     {
#         "week": "10/15/2024",
#         "items": [
#             {"name": "Salmon", "date_added": "10/16/2024", "amount": "1.5 lbs"},
#             {"name": "Sweet Potatoes", "date_added": "10/16/2024", "amount": "4"},
#             {"name": "Greek Yogurt", "date_added": "10/17/2024", "amount": "32 oz"},
#         ]
#     }
# ]


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
            current_list.append({
                "name": name,
                "amount": amount,
                "date_added": datetime.datetime.now().strftime("%m/%d/%Y")
            })
            return render_template("grocery-list.html", items=current_list)

    # Handle GET request - display grocery list
    return render_template("grocery-list.html", items=current_list)

@grocery_bp.route("/save-week")
def save_week():
    global current_list, grocery_history

    if current_list:
        formatted_items = [
            {
                "name": item["name"],
                "amount": item["amount"],
                "date_added": item["date_added"]
            }
            for item in current_list
        ]

        grocery_history.append({
            "week": datetime.datetime.now().strftime("%m/%d/%Y"),
            "items": formatted_items
        })

        current_list.clear()

    return redirect(url_for("grocery.grocery_history_page"))

@grocery_bp.route("/grocery-history")
def grocery_history_page():
    return render_template("grocery-history.html", history=grocery_history)

from flask import send_from_directory

