from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from pymongo import MongoClient
import os
import datetime
from bson.objectid import ObjectId
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
grocery_history = db["grocery_history"] #need to update to read old week's instead of hardcoded 

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

def get_week_start(dt):
    """Get the Monday of the week for a given datetime"""
    return dt - datetime.timedelta(days=dt.weekday())
def add_old_to_history(username):
    """Add Items from current_week into grocery_history"""
    #get the current week time
    now = datetime.datetime.utcnow()
    this_week_start = get_week_start(now).replace(hour=0, minute=0, second=0, microsecond=0)
    #go through current_list to find old dates
    old_items = list(current_week.find({
        "username": username,
        "date_added": {"$lt": this_week_start},
        "username": username
        }))
    old_weeks = {}
    if old_items:
        #go through each old item and find correct week group
        for item in old_items:
            item_week_start = get_week_start(item["date_added"]).replace(hour=0, minute=0, second=0, microsecond=0)
            week_key = item_week_start.strftime("%Y-%m-%d") 
            if week_key not in old_weeks:
                old_weeks[week_key]={
                    "week_start": item_week_start,
                    "items": []
                }
            #make a copy of the item from current_list 
            item_cp = item.copy()
            item_cp["_id"] = str(item["_id"])
            #add this item into its correct week
            old_weeks[week_key]["items"].append(item_cp)
    for week_key in old_weeks:
        exist = grocery_history.find_one({"week_start": old_weeks[week_key]["week_start"]})
        if exist:
            grocery_history.update_one(
                {"week_start": old_weeks[week_key]["week_start"]},
                {"$push": {"items": {"$each": old_weeks[week_key]["items"]}}}
            )
        else:
            grocery_history.insert_one({
                "username": username,
                "week_start": old_weeks[week_key]["week_start"],
                "items": old_weeks[week_key]["items"]
            })

    for item in old_items:
        current_week.delete_one({"_id":item["_id"]})
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
        item = current_week.find_one({"_id": ObjectId(item_id)})
        if item:
            username = item.get("username")
            result = current_week.delete_one({"_id": ObjectId(item_id)})
            if result.deleted_count > 0:
                print(f"Deleted item with id: {item_id}")
                # Update the weekly meal plan after deleting item
                build_meal_plan(username)
            else:
                print(f"Item not found: {item_id}")
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
            username = item.get("username")
            current_value = item.get("time_in_day", "").lower() == "breakfast"
            new_value = "empty" if current_value else "breakfast"
            current_week.update_one(
                {"_id": ObjectId(item_id)},
                {"$set": {"time_in_day": new_value, "breakfast": not current_value}}
            )
            print(f"Toggled breakfast for {item.get('name')} to {new_value}")
            
            # Update the weekly meal plan after toggling
            build_meal_plan(username)
            
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
    """Updates the grocery history page"""
    username = session.get('username')
    add_old_to_history(username)
    # Sort by week in descending order
    history = list(grocery_history.find({"username": username}).sort("week_start", -1))  
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
    username = session.get('username')
    if not username:
        return redirect(url_for("login"))
    
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
        # username = session.get('username') #NEED TO DEBUG
        # if not username:
        #     print("no user")
        #     return redirect(url_for("auth.login"))
        food_category = get_item_category(name)
        if food_category is None:
            items = current_week.find({"username": username})
            categories_dict = {}
            for item in items:
                item['_id'] = str(item['_id'])
                item['breakfast'] = item.get('time_in_day', '').lower() == 'breakfast'
                category = item.get("food_type", "other")
                if category not in categories_dict:
                    categories_dict[category] = []
                categories_dict[category].append(item)
            return render_template("grocery-list.html", 
                                   categories = categories_dict, 
                                   error = "Sorry we don't recognize this food. Please try a different food item"
                                   )

        total_calories = calculate_item_calories(name,amount)    
        print(f"POST - Name: {name}, Amount: {amount}, Breakfast: {is_breakfast} cal: {total_calories}")    

        
        if name and amount:
            
            result  = current_week.insert_one({
                "username": username,
                "name": name,
                "amount": amount,
                "time_in_day": "breakfast" if is_breakfast else "empty",
                "breakfast": is_breakfast,
                "food_type": food_category,
                "date_added": datetime.datetime.utcnow(),
                "calories": total_calories
            })

            print(f"Added item{name} ({amount}g) - Category: {food_category}")
            
            # Update the weekly meal plan after adding item
            build_meal_plan(username)
            
        return redirect(url_for("grocery.grocery_list"))
   
   # GET request

    items = current_week.find({"username": username})
    categories_dict = {}

    for item in items:
        item['_id'] = str(item['_id'])
        item['breakfast'] = item.get('time_in_day', '').lower() == 'breakfast'
        category = item.get("food_type", "other")

        if category not in categories_dict:
            categories_dict[category] = []
        categories_dict[category].append(item)

 
    return render_template("grocery-list.html", categories=categories_dict)


@grocery_bp.route('/<path:filename>')
def serve_grocery_static(filename):
    return send_from_directory('groceryDisplay', filename)


from flask import send_from_directory