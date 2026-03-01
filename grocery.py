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

@grocery_bp.route("/grocery-history")
def grocery_history_page():
    history = list(grocery_history.find().sort("week", -1))  # Sort by week in descending order
    return render_template("grocery-history.html", history=history)

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

'''
TODO:
- Add functionality to edit from the current grocery list:
    -edit name and amount within food Class, request from form and update in db. This food item will be added to currentList
    -then, search for this item in USDA db and update the calories total by amt, foodcategory, and time added.
    @return item in foodClass (category, calories, name, amount) to update the currentList and display on grocery list page under the correct category.
-Add functionality to delete from the current grocery list
-Current week's functionality:
    -count total calories for the week by summing calories of each item. As well as count total calories within each food groups
    -display current week's grocery into weekly Display page @ /weekly-display
    -add functionality to save current week's grocery list to history and clear current week for new list
    return current week's grocery into weekly Display page {without algorithm, for now just iterate through current week's grocery list and display items with calories and categories}
'''
#Add: 
# @grocery_bp.route("/grocery-list/create", methods=["GET","POST"])
# def create_grocery_item():
#     # if request.is_json: 
#     #     data = request.get_json()
#     #     name = data.get("name")
#     #     amount = data.get("amount")
#     #     if name and amount:
#     #         current_week.insert_one({
#     #             "name": name,
#     #             "food_type": 0,  # Placeholder for food type, can be updated later
#     #             "amount": amount,
#     #             "calories": 0,  # Placeholder for calories, can be updated later
#     #             "breakfast": False,  # Placeholder for time of day, can be updated later
#     #             "date_added": datetime.datetime.utcnow()
#     #         })
#     #         return {"message": "Grocery item created successfully"}, 201
#     name = request.form.get("food-name") #id of input field in grocery list page form
#     amount = request.form.get("amount")
#     if name and amount:
#         current_week.insert_one({
#             "name": name,
#             "food_type": "protein",  # Placeholder for food type, can be updated later
#             "amount": amount,
#             "calories": 0,  # Placeholder for calories, can be updated later
#             "breakfast": False,  # Placeholder for time of day, can be updated later
#             "date_added": datetime.datetime.utcnow()
#         })
#         print(f"Added item: {name}, amount: {amount} to current week's grocery list.")
#         return redirect(url_for("grocery.grocery_list"))           
#     #GET
#     items = list(current_week.find())
#     grouped = {}
#     for item in items: 
#         category = item.get("food_type", "uncategorized")
#         grouped.setdefault(category, []).append(item)
#     categories = [
#         {"name": name.capitalize(), "items": grouped[name]}
#         for name in grouped
#     ]
#     return render_template("grocery-list.html", categories=categories)
@grocery_bp.route("/grocery-list", methods=["GET", "POST"])
def grocery_list():
    print(f"Received {request.method} request at /grocery-list")
    if request.method == "POST":
        name = request.form.get("name")
        amount = request.form.get("amount")
        print(f"Received POST request with name: {name}, amount: {amount}")
        if name and amount:
            current_week.insert_one({
                "name": name,
                "food_type": "protein",
                "amount": amount,
                "calories": 0,
                "breakfast": False,
                "date_added": datetime.datetime.utcnow()
            })
        # return redirect(url_for("grocery.grocery_list"))
    # GET request
    items = list(current_week.find())
    # for i in items:
    #     print(i.get("name"))
    
    #TODO: currently, all items are categorized as protein for testing. Need to update to categorize based on food_type field in db.
    categories_dict = {
        "protein": items,  # Assuming all items are currently categorized as protein for testing
        "vegetable": [],
        "fruit": [],
        "grain": [],
        "dairy": [],
        "other": []
    }
    for category_name, items in categories_dict.items():
        print(f"Category: {category_name}")
        for item in items:
            print(item.get("name"))
    return render_template("grocery-list.html", categories=categories_dict)


from flask import send_from_directory

