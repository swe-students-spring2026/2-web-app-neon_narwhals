from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from pymongo import MongoClient
import os
import datetime
from bson.objectid import ObjectId
import certifi
from algorithm import (
    parse_grams,
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
    doc = db.foodstats.find_one({"Name": {"$regex": name, "$options": "i"}})
    grams = parse_grams(amount)
    print(doc['Calories'])
    if doc:
        return doc['Calories'] / 100 * grams
    else:
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


#== CRUD ==#
def label_existing_items():
    items = list(current_week.find({
        "$or": [
            {"food_type": {"$exists": False}},  # Field doesn't exist
            {"food_type": None},                 # Field is null
            {"food_type": "null"},                # Field is string "null"
            {"food_type": ""} ,                     # Field is empty string
            {"calories" : 0}
        ]
    }))


    updated_count = 0

    for item in items:
        name = item['name']
        amount = item['amount']
        item_id = item['_id']
        print(f"name: {name}, amt: {amount}, cal: {item['calories']}")
        if item['calories'] == 0:
            calories = calculate_item_calories(name, amount)
            result = current_week.update_one(
                {'_id': item['_id']},
                {'$set': {'calories':calories}}
            )
        else:
            food_category = get_item_category(name)
            result = current_week.update_one(
                {'_id': item['_id']},
                {'$set': {'food_type':food_category}}
            )
        if result.modified_count > 0:
            updated_count +=1
    print(f"Total items updated: {updated_count}")
    return updated_count

@grocery_bp.route("/delete-item/<item_id>", methods=["POST"])
def delete_item(item_id):
    try:
        result = current_week.delete_one({"_id": ObjectId(item_id)})
        if result.deleted_count > 0:
            print(f"Deleted item with id: {item_id}")
        else:
            print(f"Item not found: {item_id}")
    except Exception as e:
        print(f"Error deleting item: {e}")
    return redirect(url_for("grocery.grocery_list"))

@grocery_bp.route("/toggle-breakfast/<item_id>", methods=["POST"])
def toggle_breakfast(item_id):
    try:
        item = current_week.find_one({"_id": ObjectId(item_id)})
        if item:
            current_value = item.get("breakfast", False)
            current_week.update_one(
                {"_id": ObjectId(item_id)},
                {"$set": {"breakfast": not current_value}}
            )
            print(f"Toggled breakfast for {item.get('name')} to {not current_value}")
            
            if request.headers.get('Content-Type') == 'application/json':
                return jsonify({"success": True, "breakfast": not current_value})
        
        return redirect(url_for("grocery.grocery_list"))
    except Exception as e:
        print(f"Error toggling breakfast: {e}")
        return redirect(url_for("grocery.grocery_list"))

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
    unlabeled_items = current_week.count_documents({
    "$or": [
        {"food_type": {"$exists": False}},
        {"food_type": None},
        {"food_type": ""},
        {"food_type": "null"},
        {"calories": 0}
    ]
    })
    
    if unlabeled_items > 0:
        print(f"Found {unlabeled_items} unlabeled items. Labeling them now...")
        label_existing_items()
    

    print(f"Received {request.method} request at /grocery-list")
    if request.method == "POST":
        name = request.form.get("name")
        amount = request.form.get("amount")
        is_breakfast = request.form.get("breakfast") == "on"
        username = session.get('username', 'default_user')
        food_category = get_item_category(name)
        total_calories = calculate_item_calories(name,amount)    
        print(f"POST - Name: {name}, Amount: {amount}, Breakfast: {is_breakfast} cal: {total_calories}")    

        
        if name and amount:
            
            result  = current_week.insert_one({
                "username": username,
                "name": name,
                "amount": amount,
                "time_in_day": "breakfast" if is_breakfast else "empty",
                "food_type": food_category,
                "date_added": datetime.datetime.utcnow(),
                "calories": total_calories
            })

            print(f"Added item{name} ({amount}g) - Category: {food_category}")
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