from flask import Blueprint, render_template, request, redirect, url_for, session
from pymongo import MongoClient
import os
import datetime
import certifi
from algorithm import (
    build_meal_plan,
    push_weekly_plan,
    get_food_category,
    lookup_food_category,
    get_calories_per_gram,
    parse_grams
)
'''
This module defines the grocery blueprint for the Flask application. It handles routes related to the grocery list, including displaying the current list, adding items, saving weekly history, and viewing past grocery lists.
'''
client = MongoClient(
    os.getenv("MONGO_URI"),
    tlsCAFile=certifi.where()  # Add SSL certificate verification
)


grocery_bp = Blueprint('grocery', __name__, template_folder='groceryDisplay')
db = client["groceryfood"]


current_week = db["current_list"]
grocery_history = db["grocery_list_test"] #need to update to read old week's instead of hardcoded 

#== HELPER FUNCTIONS ==#
def calculate_item_calories(name, amount):
    calories_per_gram = get_calories_per_gram(name)
    grams = parse_grams(amount)
    if calories_per_gram is not None and grams > 0:
        return round(calories_per_gram * grams, 1)
    return 0

def get_item_category(name):
    category  = db.foodstats.find_one({"Name": {"$regex": name, "$options": "i"}})
    # doc = food_db.foodstats.find({"Name": {"$regex": food_name}})
    if category:
        print(category["Category"])
        return category["Category"]
    else:
        print("not found!")
        return None
    # category = get_food_category(name)
    # print(category)
    # if not category  or category == "Unknown":
    #     food = lookup_food_category(name)
    #     if food:
    #         return food.get("Category", "other").lower()
    #     return "other"
    # return category.lower()


#== CRUD ==#
def label_existing_items():
    items = list(current_week.find({
        "$or": [
            {"food_type": {"$exists": False}},  # Field doesn't exist
            {"food_type": None},                 # Field is null
            {"food_type": "null"},                # Field is string "null"
            {"food_type": ""}                      # Field is empty string
        ]
    }))


    updated_count = 0

    for item in items:
        name = item['name']
        item_id = item['_id']
        if name:
            food_category = get_item_category(name)
            result = current_week.update_one(
                {'_id': item['_id']},
                {'$set': {'food_type':food_category}}
            )

            if result.modified_count > 0:
                updated_count +=1
                (f"Updated {name} with category: {food_category}")
    print(f"Total items updated: {updated_count}")
    return updated_count

@grocery_bp.route("/label-items")
def label_items_route():
    count = label_existing_items()
    return  f"Updated {count} items with food categories."  
#== GROCERY DISPLAY ==#
@grocery_bp.route("/grocery-history")
def grocery_history_page():
    history = list(grocery_history.find().sort("week", -1))  # Sort by week in descending order
    
    for week in history:
        week['_id'] = str(week['_id'])
        for item in week.get('items', []):
            item['_id'] = str(item['_id'])
    return render_template("grocery-history.html", history=history)

@grocery_bp.route("/save-week") #hasn't implement function yet
def save_week():
    items = list(current_week.find())
    if items:
        items_for_history = []
        for item in items:
            item_copy = item.copy()
            item_copy['_id'] = str(item_copy['_id'])
            items_for_history.append(item_copy)

        grocery_history.insert_one({
            "week": datetime.datetime.utcnow(),
            "items": items_for_history
        })
        #if copy current items to history, then clear current week as week is over
        current_week.delete_many({})
    return redirect(url_for("grocery.grocery_history_page"))



@grocery_bp.route("/grocery-list", methods=["GET", "POST"])
def grocery_list():
    unlabeled_items = current_week.count_documents({"food_type": {"$exists": "null"} })
    
    if unlabeled_items > 0:
        print(f"Found {unlabeled_items} unlabeled items. Labeling them now...")
        label_existing_items()
    

    print(f"Received {request.method} request at /grocery-list")
    if request.method == "POST":
        name = request.form.get("name")
        amount = request.form.get("amount")
        # time_in_day = request.form.get("breakfast") #TODO: request form for breakfast
        # username = session.get('username', 'default_user')
        print(f"Received POST request with name: {name}, amount: {amount}")
        if name and amount: #try reusing james algo.py
            food_category = get_item_category(name)
            total_calories = calculate_item_calories(name,amount)

            result  = current_week.insert_one({
                "username": "userTest",
                "name": name,
                "food_type": food_category,
                "amount": amount,
                "calories": total_calories,
                # "time_in_day": time_in_day, #function get breakfast
                "date_added": datetime.datetime.utcnow()
            })
            print(f"Added item{name} ({amount}g) - Category: {food_category}, Calories: {total_calories}")
        return redirect(url_for("grocery.grocery_list"))
    # GET request

    items = list(current_week.find())
    categories_dict = {}

    for item in items:
        item['_id'] = str(item['_id'])
        category = item.get("food_type", "other")
        if category not in categories_dict:
            categories_dict[category] = []
        categories_dict[category].append(item)

 
    return render_template("grocery-list.html", categories=categories_dict, total_items = len(items))


@grocery_bp.route('/<path:filename>')
def serve_grocery_static(filename):
    return send_from_directory('groceryDisplay', filename)


from flask import send_from_directory