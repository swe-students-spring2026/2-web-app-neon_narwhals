#!/usr/bin/env python3

"""
Example flask-based web application.
See the README.md file for instructions how to set up and run the app in development mode.
"""

import os
import datetime
#from flask import Flask, render_template, request, redirect, url_for
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory, session
import pymongo
from bson.objectid import ObjectId
from dotenv import load_dotenv, dotenv_values
from jinja2 import ChoiceLoader, FileSystemLoader
from grocery import grocery_bp
import certifi
from pymongo import MongoClient



load_dotenv()  # load environment variables from .env file
class Food:
    """
    Food class to represent a food item with nutritional and timing information.
    """
    def __init__(self, name, food_type, food_amount, calorie_amount, weekday, time_in_day):
        self.name = name
        self.food_type = food_type  # protein, vegetable, carbohydrate, etc.
        self.food_amount = food_amount  # in grams
        self.calorie_amount = calorie_amount  # calories
        self.weekday = weekday  # monday, tuesday, etc.
        self.time_in_day = time_in_day  # breakfast, lunch, dinner
        self.created_at = datetime.datetime.utcnow()
    def to_dict(self):
        """Convert Food object to dictionary for MongoDB storage."""
        return {
            "name": self.name,
            "food_type": self.food_type,
            "food_amount": self.food_amount,
            "calorie_amount": self.calorie_amount,
            "weekday": self.weekday,
            "time_in_day": self.time_in_day,
            "created_at": self.created_at
        }


def create_app():
    """
    Create and configure the Flask application.
    returns: app: the Flask application object
    """

    app = Flask(__name__)
    # Configure template loaders for multiple directories
    app.jinja_loader = ChoiceLoader([
        FileSystemLoader('templates'),  # For login.html
        FileSystemLoader('weeklyDisplay'),  # For existing templates
    ])
    # load flask config from env variables
    config = dotenv_values()
    app.config.from_mapping(config)
    # Set up session secret key
    app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

    cxn = pymongo.MongoClient(os.getenv("MONGO_URI"))
    cxn = pymongo.MongoClient(
    os.getenv("MONGO_URI"),
    tlsCAFile=certifi.where()  # This fixes the SSL certificate error
)
    db = cxn[os.getenv("MONGO_DBNAME")]
   # Attach db to app for use in routes defined outside create_app
    app.db = db

    try:
        cxn.admin.command("ping")
        print(" *", "Connected to MongoDB!")
        if cxn is not None:
            cxn.admin.command("ping")
            print(" *", "Connected to MongoDB!")
        # Create a sample Food object and insert it into the database
        sample_food = Food(
            name="beef",
            food_type="protein",
            food_amount=150,  # grams
            calorie_amount=250,  # calories
            weekday="monday",
            time_in_day="dinner"
        )
        # Check if this food item already exists to avoid duplicates
        existing_food = db.foods.find_one({"name": sample_food.name, "weekday": sample_food.weekday, "time_in_day": sample_food.time_in_day})
        if not existing_food:
            db.foods.insert_one(sample_food.to_dict())
            print(" *", f"Sample food '{sample_food.name}' created and stored in database!")
        else:
            print(" *", f"Sample food '{sample_food.name}' already exists in database.")
    except Exception as e:
        print(" * MongoDB connection error:", e)

    app.register_blueprint(grocery_bp)
    @app.route("/")
    @app.route("/week")
    def home():
        """
        Route for the home page - displays weekly food view.
        Returns:
            HTML template or JSON response with weekly food data.
        """
        # Check if user is logged in
        username = session.get('username')
        if not username:
            return redirect(url_for("login"))

        # First try to get data from weeklymeals collection (generated plans)
        weekly_plan_doc = db.weeklymeals.find_one({"username": username})
        if weekly_plan_doc and "plan" in weekly_plan_doc:
            # Use generated meal plan data
            plan = weekly_plan_doc["plan"]
            # Ensure all days are in the plan
            weekday_display = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            for day_name in weekday_display:
                if day_name not in plan:
                    plan[day_name] = {
                        'Breakfast': {'items': [], 'total_calories': 0},
                        'Lunch': {'items': [], 'total_calories': 0},
                        'Dinner': {'items': [], 'total_calories': 0}
                    }
            # Update if changed
            if plan != weekly_plan_doc["plan"]:
                db.weeklymeals.update_one({"username": username}, {"$set": {"plan": plan}})
            week_days = []
            weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            weekday_display = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

            # Get current day for highlighting
            today_weekday = datetime.datetime.now().strftime('%A').lower()

            for i, weekday in enumerate(weekdays):
                day_name = weekday_display[i]
                day_plan = plan.get(day_name, {})

                # Convert algorithm format to template format
                meals = {}
                for meal_name in ['Breakfast', 'Lunch', 'Dinner']:
                    meal_data = day_plan.get(meal_name, {})
                    meals[meal_name.lower()] = [
                        {
                            'name': item['foodName'],
                            'food_type': item.get('foodCategory', 'Unknown'),
                            'food_amount': item['grams'],
                            'calorie_amount': item['calories'],
                            'weekday': weekday,
                            'time_in_day': meal_name.lower(),
                            'username': username,
                            'is_generated': True
                        }
                        for item in meal_data.get('items', [])
                    ]

                day_data = {
                    'name': day_name,
                    'full_name': weekday,
                    'is_today': weekday == today_weekday,
                    'meals': meals
                }
                week_days.append(day_data)

            # Check if request wants JSON (API usage)
            if request.headers.get('Content-Type') == 'application/json' or request.args.get('format') == 'json':
                # Convert to JSON format
                foods_list = []
                for day_data in week_days:
                    for meal_name, meal_items in day_data['meals'].items():
                        foods_list.extend(meal_items)
                return jsonify({"foods": foods_list, "source": "generated_plan"})
        else:
            # Fall back to manual foods collection
            food_docs = list(db.foods.find({"username": username}).sort("created_at", -1))
            # Check if request wants JSON (API usage)
            if request.headers.get('Content-Type') == 'application/json' or request.args.get('format') == 'json':
                # Convert ObjectId to string for JSON serialization
                for doc in food_docs:
                    doc['_id'] = str(doc['_id'])
                return jsonify({"foods": food_docs, "source": "manual_foods"})

            # Organize foods by weekday and meal time for weekly view
            week_days = []
            weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            weekday_display = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            # Get current day for highlighting
            today_weekday = datetime.datetime.now().strftime('%A').lower()
            for i, weekday in enumerate(weekdays):
                # Filter foods for this weekday
                day_foods = [food for food in food_docs if food.get('weekday', '').lower() == weekday]
                # Organize by meal time
                meals = {
                    'breakfast': [food for food in day_foods if food.get('time_in_day', '').lower() == 'breakfast'],
                    'lunch': [food for food in day_foods if food.get('time_in_day', '').lower() == 'lunch'],
                    'dinner': [food for food in day_foods if food.get('time_in_day', '').lower() == 'dinner']
                }
                day_data = {
                    'name': weekday_display[i],
                    'full_name': weekday,
                    'is_today': weekday == today_weekday,
                    'meals': meals
                }
                week_days.append(day_data)

        # Week navigation data
        week_label = "Current Week"
        week_sub_label = datetime.datetime.now().strftime("%B %d, %Y")
        # Return HTML template for web interface
        return render_template("simple-week.html",
                             week_days=week_days,
                             week_label=week_label,
                             week_sub_label=week_sub_label,
                             prev_week_url="#",  # Placeholder for now
                             next_week_url="#",  # Placeholder for now
                             today_weekday=today_weekday)

    @app.route("/day", defaults={'weekday': None})
    @app.route("/day/<weekday>")
    def day_view(weekday):
        """
        Route for individual day view for adding/editing meals.
        Args:
            weekday (str): The weekday to display, defaults to today if None
        Returns:
            HTML template with day-specific food form
        """
        username = session.get('username')
        if not username:
            return redirect(url_for("login"))
        if weekday is None:
            weekday = datetime.datetime.now().strftime('%A').lower()

        # First try to get data from weeklymeals collection (generated plans)
        weekly_plan_doc = db.weeklymeals.find_one({"username": username})
        if weekly_plan_doc and "plan" in weekly_plan_doc:
            # Use generated meal plan data
            plan = weekly_plan_doc["plan"]
            weekday_display = weekday.title()

            # Find the day in the plan (case-insensitive match)
            day_plan = None
            for day_name in plan.keys():
                if day_name.lower() == weekday.lower():
                    day_plan = plan[day_name]
                    weekday_display = day_name
                    break

            if day_plan:
                # Convert algorithm format to template format
                meals = {}
                total_calories = 0
                total_protein = 0

                for meal_name in ['Breakfast', 'Lunch', 'Dinner']:
                    meal_data = day_plan.get(meal_name, {})
                    meal_items = []

                    for item in meal_data.get('items', []):
                        food_item = {
                            'name': item['foodName'],
                            'food_type': item.get('foodCategory', 'Unknown'),
                            'food_amount': item['grams'],
                            'calorie_amount': item['calories'],
                            'weekday': weekday.lower(),
                            'time_in_day': meal_name.lower(),
                            'username': username,
                            'is_generated': True
                        }
                        meal_items.append(food_item)
                        total_calories += item['calories']
                        if item.get('foodCategory') == 'Protein Foods':
                            total_protein += item['grams']

                    meals[meal_name.lower()] = meal_items
            else:
                # Day not found in plan
                meals = {'breakfast': [], 'lunch': [], 'dinner': []}
                total_calories = 0
                total_protein = 0
        else:
            # Fall back to manual foods collection
            # Get foods for this specific day
            day_foods = list(db.foods.find({"weekday": weekday.lower(), "username": username}).sort("created_at", -1))
            # Organize by meal time
            meals = {
                'breakfast': [food for food in day_foods if food.get('time_in_day', '').lower() == 'breakfast'],
                'lunch': [food for food in day_foods if food.get('time_in_day', '').lower() == 'lunch'],
                'dinner': [food for food in day_foods if food.get('time_in_day', '').lower() == 'dinner']
            }
            # Calculate basic summary
            total_calories = sum(food.get('calorie_amount', 0) for food in day_foods)
            total_protein = sum(food.get('food_amount', 0) for food in day_foods if food.get('food_type') == 'protein')
            weekday_display = weekday.title()

        # Day navigation
        weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        current_index = weekdays.index(weekday.lower()) if weekday.lower() in weekdays else 0
        prev_weekday = weekdays[(current_index - 1) % 7]
        next_weekday = weekdays[(current_index + 1) % 7]
        date_label = datetime.datetime.now().strftime("%B %d, %Y")
        return render_template("simple-day.html",
                             weekday=weekday.lower(),
                             weekday_display=weekday_display,
                             date_label=date_label,
                             prev_weekday=prev_weekday,
                             next_weekday=next_weekday,
                             meals=meals,
                             protein=total_protein,
                             carbs=0,  # Placeholder
                             fiber=0,  # Placeholder
                             sugar=0,  # Placeholder
                             calories=total_calories,
                             today_weekday=weekday.lower())

    @app.route("/add-item")
    def add_item():
        """
        Route for adding a new food item with pre-selected weekday and meal.
        Returns:
            HTML form for adding food item
        """
        weekday = request.args.get('weekday', 'monday')
        meal = request.args.get('meal', 'breakfast')
        # Create a form template matching simple-week.html style
        return f'''
        <!DOCTYPE html>
        <html lang="en">
        <head>
          <meta charset="UTF-8" />
          <meta name="viewport" content="width=393, initial-scale=1.0" />
          <title>MealPrep – Add Item</title>
          <link rel="stylesheet" href="week.css" />
          <style>
            .form-container {{
              padding: 20px;
              max-width: 100%;
            }}
            .form-header {{
              text-align: center;
              padding: 12px 0 20px 0;
              font-size: 18px;
              font-weight: 600;
            }}
            .context-info {{
              background: #f8f9fa;
              padding: 12px 16px;
              border-radius: 8px;
              margin-bottom: 20px;
              font-size: 14px;
              border-left: 3px solid #007AFF;
            }}
            .form-group {{
              margin-bottom: 16px;
            }}
            .form-group label {{
              display: block;
              margin-bottom: 6px;
              font-weight: 500;
              color: #333;
            }}
            .form-group input,
            .form-group select {{
              width: 100%;
              padding: 12px;
              border: 1px solid #ddd;
              border-radius: 8px;
              font-size: 14px;
              background: #fff;
            }}
            .form-group input:focus,
            .form-group select:focus {{
              outline: none;
              border-color: #007AFF;
              box-shadow: 0 0 0 2px rgba(0, 122, 255, 0.1);
            }}
            .button-row {{
              display: flex;
              gap: 12px;
              margin-top: 24px;
            }}
            .btn {{
              flex: 1;
              padding: 12px 16px;
              border: none;
              border-radius: 8px;
              font-size: 14px;
              font-weight: 500;
              cursor: pointer;
              text-decoration: none;
              text-align: center;
              display: inline-block;
            }}
            .btn-primary {{
              background: #007AFF;
              color: white;
            }}
            .btn-primary:hover {{
              background: #0056b3;
            }}
            .btn-secondary {{
              background: #f8f9fa;
              color: #333;
              border: 1px solid #ddd;
            }}
            .btn-secondary:hover {{
              background: #e9ecef;
            }}
          </style>
        </head>
        <body>
        <div class="screen">
        <div class="scroll-area">

          <div class="status-bar">
            <span>9:41</span>
            <span>●●●</span>
          </div>

          <div class="page-header">Add Food Item</div>

          <div class="content">
            <div class="form-container">
              
              <div class="context-info">
                <strong>Adding to:</strong> {weekday.title()} - {meal.title()}
              </div>
              
              <form action="/create" method="POST">
                <input type="hidden" name="weekday" value="{weekday}">
                <input type="hidden" name="time_in_day" value="{meal}">
                
                <div class="form-group">
                  <label for="name">Food Name</label>
                  <input type="text" id="name" name="name" placeholder="e.g. Grilled Chicken" required>
                </div>
                
                <div class="form-group">
                  <label for="food_type">Food Type</label>
                  <select id="food_type" name="food_type" required>
                    <option value="protein">Protein</option>
                    <option value="vegetable">Vegetable</option>
                    <option value="fruit">Fruit</option>
                    <option value="carbohydrate">Carbohydrate</option>
                    <option value="dairy">Dairy</option>
                    <option value="grain">Grain</option>
                    <option value="snack">Snack</option>
                  </select>
                </div>
                
                <div class="form-group">
                  <label for="food_amount">Amount (grams)</label>
                  <input type="number" id="food_amount" name="food_amount" min="1" placeholder="100" required>
                </div>
                
                <div class="form-group">
                  <label for="calorie_amount">Calories</label>
                  <input type="number" id="calorie_amount" name="calorie_amount" min="0" placeholder="150" required>
                </div>
                
                <div class="button-row">
                  <button type="submit" class="btn btn-primary">Add Food Item</button>
                  <a href="/week" class="btn btn-secondary">Cancel</a>
                </div>
              </form>
            </div>
          </div>

        </div><!-- end scroll-area -->

          <!-- Bottom Nav — always visible, outside scroll -->
          <nav class="bottom-nav">
            <a href="/"    class="nav-tab">Home</a>
            <a href="/week" class="nav-tab active">Week</a>
            <a href="/day/{weekday}" class="nav-tab">Day</a>
          </nav>

        </div><!-- end screen -->
        </body>
        </html>
        '''

    @app.route("/delete-day/<weekday>", methods=["POST"])
    def delete_day(weekday):
        """
        Route to delete all meals for a specific day.
        Args:
            weekday (str): The weekday to clear
        Returns:
            Redirect to home page
        """
        username = session.get('username')
        if not username:
            return redirect(url_for("login"))
        db.foods.delete_many({"weekday": weekday.lower(), "username": username})
        
        # Also delete from weeklymeals if it exists
        weekly_plan = db.weeklymeals.find_one({"username": username})
        if weekly_plan and 'plan' in weekly_plan:
            plan = weekly_plan['plan']
            # Find the correct key (case-insensitive)
            day_key = None
            for key in plan.keys():
                if key.lower() == weekday.lower():
                    day_key = key
                    break
            if day_key:
                # Set the day to empty meals instead of deleting
                plan[day_key] = {
                    'Breakfast': {'items': [], 'total_calories': 0},
                    'Lunch': {'items': [], 'total_calories': 0},
                    'Dinner': {'items': [], 'total_calories': 0}
                }
                db.weeklymeals.update_one({"username": username}, {"$set": {"plan": plan}})
        
        return redirect(url_for("home"))

    @app.route("/delete-meal/<weekday>/<meal>", methods=["POST"])
    def delete_meal(weekday, meal):
        """
        Route to delete all foods for a specific meal.
        Args:
            weekday (str): The weekday
            meal (str): The meal time (breakfast, lunch, dinner)
        Returns:
            Redirect to day view
        """
        username = session.get('username')
        if not username:
            return redirect(url_for("login"))
        db.foods.delete_many({"weekday": weekday.lower(), "time_in_day": meal.lower(), "username": username})
        return redirect(url_for("day_view", weekday=weekday))

    @app.route("/swap-day/<weekday>", methods=["POST"])
    def swap_day(weekday):
        """
        Route to swap meals within a day
        Args:
            weekday (str): The weekday to swap
        Returns:
            Redirect to day view
        """
        return redirect(url_for("day_view", weekday=weekday))

    @app.route("/week/swap/<weekday>/<direction>", methods=["POST"])
    def swap_week_day(weekday, direction):
        """
        Swap all meals for one day with the day above or below it in the week view

        Args:
            weekday (str): name like 'monday', 'tuesday', etc. (from template day.full_name)
            direction (str): 'up' or 'down'
        """
        weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        day = weekday.lower()
        if day not in weekdays:
            return redirect(url_for("home"))

        idx = weekdays.index(day)
        if direction == "up":
            if idx == 0:
                return redirect(url_for("home"))
            other = weekdays[idx - 1]
        else:  # treat anything else as down
            if idx == len(weekdays) - 1:
                return redirect(url_for("home"))
            other = weekdays[idx + 1]

        # swap weekday field between this day and the neighbour using a temporary label
        tmp = "__tmp_swap__"
        db.foods.update_many({"weekday": day}, {"$set": {"weekday": tmp}})
        db.foods.update_many({"weekday": other}, {"$set": {"weekday": day}})
        db.foods.update_many({"weekday": tmp}, {"$set": {"weekday": other}})

        # Also swap in weeklymeals if it exists
        username = session.get('username')
        if username:
            weekly_plan = db.weeklymeals.find_one({"username": username})
            if weekly_plan and 'plan' in weekly_plan:
                plan = weekly_plan['plan']
                # Find the correct keys (case-insensitive)
                day_key = None
                other_key = None
                for key in plan.keys():
                    if key.lower() == day:
                        day_key = key
                    elif key.lower() == other:
                        other_key = key
                if day_key and other_key:
                    # Swap the day plans
                    plan[day_key], plan[other_key] = plan[other_key], plan[day_key]
                    db.weeklymeals.update_one({"username": username}, {"$set": {"plan": plan}})

        return redirect(url_for("home"))

    @app.route("/day/swap/<weekday>/<meal>/<direction>", methods=["POST"])
    def swap_day_meal(weekday, meal, direction):
        """
        Swap a meal with the adjacent meal in the day view

        Args:
            weekday (str): name like 'monday', 'tuesday', etc.
            meal (str): 'breakfast', 'lunch', or 'dinner'
            direction (str): 'up' or 'down'
        """
        username = session.get('username')
        if not username:
            return redirect(url_for("login"))
        
        meals = ["breakfast", "lunch", "dinner"]
        meal = meal.lower()
        if meal not in meals:
            return redirect(url_for("day_view", weekday=weekday))

        idx = meals.index(meal)
        if direction == "up":
            if idx == 0:
                return redirect(url_for("day_view", weekday=weekday))
            target = meals[idx - 1]
        else:  # down
            if idx == len(meals) - 1:
                return redirect(url_for("day_view", weekday=weekday))
            target = meals[idx + 1]

        # swap time_in_day field between this meal and the target using a temporary label
        tmp = "__tmp_swap_meal__"
        db.foods.update_many({"weekday": weekday.lower(), "time_in_day": meal, "username": username}, {"$set": {"time_in_day": tmp}})
        db.foods.update_many({"weekday": weekday.lower(), "time_in_day": target, "username": username}, {"$set": {"time_in_day": meal}})
        db.foods.update_many({"weekday": weekday.lower(), "time_in_day": tmp, "username": username}, {"$set": {"time_in_day": target}})

        return redirect(url_for("day_view", weekday=weekday))

    @app.route("/delete-week", methods=["POST"])
    def delete_week():
        """
        Route to delete all meals for the entire week.
        Returns:
            Redirect to home page
        """
        username = session.get('username')
        if not username:
            return redirect(url_for("login"))
        db.foods.delete_many({"username": username})
        return redirect(url_for("home"))

    @app.route('/<path:filename>')
    def serve_static(filename):
        """
        Serve CSS and other static files from weeklyDisplay directory.
        """
        return send_from_directory('weeklyDisplay', filename)

    @app.route("/create", methods=["POST"])
    def create_food():
        """
        Route for POST requests to create a new food item.
        Accepts both JSON data (API) and form data (HTML).
        Returns:
            JSON response or redirect to home page.
        """
        username = session.get('username')
        if not username:
            return redirect(url_for("login"))
        # Handle JSON API requests
        if request.is_json:
            data = request.get_json()
            food = Food(
                data["name"],
                data["food_type"],
                int(data["food_amount"]),
                int(data["calorie_amount"]),
                data["weekday"],
                data["time_in_day"]
            )
            food_dict = food.to_dict()
            food_dict["username"] = username
            result = db.foods.insert_one(food_dict)
            return jsonify({"message": "Food created successfully", "id": str(result.inserted_id)})
        # Handle HTML form submissions
        else:
            name = request.form["name"]
            food_type = request.form["food_type"]
            food_amount = int(request.form["food_amount"])
            calorie_amount = int(request.form["calorie_amount"])
            weekday = request.form["weekday"]
            time_in_day = request.form["time_in_day"]

            food = Food(name, food_type, food_amount, calorie_amount, weekday, time_in_day)
            food_dict = food.to_dict()
            food_dict["username"] = username
            db.foods.insert_one(food_dict)

            # Check if we should redirect to day view or week view
            redirect_to_day = request.form.get("redirect_to_day")
            if redirect_to_day:
                return redirect(url_for("day_view", weekday=weekday))
            else:
                # Default redirect to week view for simple-week.html integration
                return redirect(url_for("home"))

    @app.route("/edit/<food_id>")
    def edit(food_id):
        """
        Route for GET requests to get a food item for editing.
        Returns the food item data as JSON or HTML template.
        Args:
            food_id (str): The ID of the food item to retrieve.
        Returns:
            JSON response or HTML template with food item data.
        """
        username = session.get('username')
        if not username:
            return redirect(url_for("login"))
        food_doc = db.foods.find_one({"_id": ObjectId(food_id), "username": username})
        if not food_doc:
            if request.headers.get('Content-Type') == 'application/json' or request.args.get('format') == 'json':
                return jsonify({"error": "Food item not found"}), 404
            else:
                return f"<h1>Error: Food item not found</h1><a href='/'>Back to Home</a>", 404
        # Handle JSON API requests
        if request.headers.get('Content-Type') == 'application/json' or request.args.get('format') == 'json':
            food_doc['_id'] = str(food_doc['_id'])
            return jsonify({"food": food_doc})
        # Return HTML form for editing
        return f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Edit Food Item</title>
            <link rel="stylesheet" href="styles.css">
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 500px; margin: 50px auto; padding: 20px; }}
                .form-group {{ margin-bottom: 15px; }}
                label {{ display: block; margin-bottom: 5px; font-weight: bold; }}
                input, select {{ width: 100%; padding: 10px; border: 2px solid #ddd; border-radius: 5px; }}
                button {{ background-color: #007AFF; color: white; padding: 12px 20px; border: none; border-radius: 5px; cursor: pointer; margin-right: 10px; }}
                button:hover {{ background-color: #0056b3; }}
                .cancel-btn {{ background-color: #666; }}
                .cancel-btn:hover {{ background-color: #555; }}
                .delete-btn {{ background-color: #ff3b30; }}
                .delete-btn:hover {{ background-color: #d70015; }}
            </style>
        </head>
        <body>
            <h2>Edit Food Item</h2>
            <form action="/edit/{food_doc['_id']}" method="POST">
                <div class="form-group">
                    <label for="name">Food Name:</label>
                    <input type="text" id="name" name="name" value="{food_doc['name']}" required>
                </div>
                
                <div class="form-group">
                    <label for="food_type">Food Type:</label>
                    <select id="food_type" name="food_type" required>
                        <option value="protein" {"selected" if food_doc.get('food_type') == 'protein' else ""}>Protein</option>
                        <option value="vegetable" {"selected" if food_doc.get('food_type') == 'vegetable' else ""}>Vegetable</option>
                        <option value="fruit" {"selected" if food_doc.get('food_type') == 'fruit' else ""}>Fruit</option>
                        <option value="carbohydrate" {"selected" if food_doc.get('food_type') == 'carbohydrate' else ""}>Carbohydrate</option>
                        <option value="dairy" {"selected" if food_doc.get('food_type') == 'dairy' else ""}>Dairy</option>
                        <option value="grain" {"selected" if food_doc.get('food_type') == 'grain' else ""}>Grain</option>
                        <option value="snack" {"selected" if food_doc.get('food_type') == 'snack' else ""}>Snack</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label for="food_amount">Amount (grams):</label>
                    <input type="number" id="food_amount" name="food_amount" value="{food_doc.get('food_amount', '')}" min="1" required>
                </div>
                
                <div class="form-group">
                    <label for="calorie_amount">Calories:</label>
                    <input type="number" id="calorie_amount" name="calorie_amount" value="{food_doc.get('calorie_amount', '')}" min="0" required>
                </div>
                
                <div class="form-group">
                    <label for="weekday">Weekday:</label>
                    <select id="weekday" name="weekday" required>
                        <option value="monday" {"selected" if food_doc.get('weekday') == 'monday' else ""}>Monday</option>
                        <option value="tuesday" {"selected" if food_doc.get('weekday') == 'tuesday' else ""}>Tuesday</option>
                        <option value="wednesday" {"selected" if food_doc.get('weekday') == 'wednesday' else ""}>Wednesday</option>
                        <option value="thursday" {"selected" if food_doc.get('weekday') == 'thursday' else ""}>Thursday</option>
                        <option value="friday" {"selected" if food_doc.get('weekday') == 'friday' else ""}>Friday</option>
                        <option value="saturday" {"selected" if food_doc.get('weekday') == 'saturday' else ""}>Saturday</option>
                        <option value="sunday" {"selected" if food_doc.get('weekday') == 'sunday' else ""}>Sunday</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label for="time_in_day">Time of Day:</label>
                    <select id="time_in_day" name="time_in_day" required>
                        <option value="breakfast" {"selected" if food_doc.get('time_in_day') == 'breakfast' else ""}>Breakfast</option>
                        <option value="lunch" {"selected" if food_doc.get('time_in_day') == 'lunch' else ""}>Lunch</option>
                        <option value="dinner" {"selected" if food_doc.get('time_in_day') == 'dinner' else ""}>Dinner</option>
                        <option value="snack" {"selected" if food_doc.get('time_in_day') == 'snack' else ""}>Snack</option>
                    </select>
                </div>
                
                <button type="submit">Save Changes</button>
                <a href="/day/{food_doc.get('weekday', 'monday')}">
                    <button type="button" class="cancel-btn">Cancel</button>
                </a>
                <a href="/delete/{food_doc['_id']}" onclick="return confirm('Are you sure you want to delete this food item?')">
                    <button type="button" class="delete-btn">Delete</button>
                </a>
            </form>
        </body>
        </html>
        '''

    @app.route("/edit/<food_id>", methods=["POST"])
    def edit_food(food_id):
        """
        Route for POST requests to update a food item.
        Accepts both JSON data (API) and form data (HTML).
        Args:
            food_id (str): The ID of the food item to edit.
        Returns:
            JSON response or redirect to home page.
        """
        username = session.get('username')
        if not username:
            return redirect(url_for("login"))
        # Handle JSON API requests
        if request.is_json:
            data = request.get_json()
            updated_food = {
                "name": data["name"],
                "food_type": data["food_type"],
                "food_amount": int(data["food_amount"]),
                "calorie_amount": int(data["calorie_amount"]),
                "weekday": data["weekday"],
                "time_in_day": data["time_in_day"],
                "created_at": datetime.datetime.utcnow(),
            }

            result = db.foods.update_one({"_id": ObjectId(food_id), "username": username}, {"$set": updated_food})
            if result.matched_count > 0:
                return jsonify({"message": "Food updated successfully"})
            else:
                return jsonify({"error": "Food item not found"}), 404
        # Handle HTML form submissions
        else:
            name = request.form["name"]
            food_type = request.form["food_type"]
            food_amount = int(request.form["food_amount"])
            calorie_amount = int(request.form["calorie_amount"])
            weekday = request.form["weekday"]
            time_in_day = request.form["time_in_day"]

            updated_food = {
                "name": name,
                "food_type": food_type,
                "food_amount": food_amount,
                "calorie_amount": calorie_amount,
                "weekday": weekday,
                "time_in_day": time_in_day,
                "created_at": datetime.datetime.utcnow(),
            }

            result = db.foods.update_one({"_id": ObjectId(food_id), "username": username}, {"$set": updated_food})
            if result.matched_count > 0:
                return redirect(url_for("day_view", weekday=weekday))
            else:
                return f"<h1>Error: Food item not found</h1><a href='/'>Back to Home</a>", 404

    @app.route("/delete/<food_id>")
    def delete(food_id):
        """
        Route for DELETE/GET requests to delete a food item.
        Deletes the specified food record from the database.
        Args:
            food_id (str): The ID of the food item to delete.
        Returns:
            JSON response or redirect to appropriate page.
        """
        username = session.get('username')
        if not username:
            return redirect(url_for("login"))
        # Get the food item first to know which day to redirect to
        food_doc = db.foods.find_one({"_id": ObjectId(food_id), "username": username})
        weekday = food_doc.get('weekday', 'monday') if food_doc else 'monday'
        result = db.foods.delete_one({"_id": ObjectId(food_id), "username": username})
        # Handle JSON API requests
        if request.headers.get('Content-Type') == 'application/json' or request.args.get('format') == 'json':
            if result.deleted_count > 0:
                return jsonify({"message": "Food deleted successfully"})
            else:
                return jsonify({"error": "Food item not found"}), 404
        # Handle HTML requests - redirect to day view if we came from day view, otherwise home
        referrer = request.headers.get('Referer', '')
        if '/day/' in referrer:
            return redirect(url_for("day_view", weekday=weekday))
        else:
            return redirect(url_for("home"))

    @app.route("/delete-by-content/<food_name>/<weekday>/<time_in_day>", methods=["POST"])
    def delete_by_content(food_name, weekday, time_in_day):
        """
        Route for POST requests to delete food items by their name, weekday, and time.
        Deletes the specified food records from the database.
        Args:
            food_name (str): The name of the food item.
            weekday (str): The weekday of the food item.
            time_in_day (str): The time in day of the food item.
        Returns:
            Redirect to home page.
        """
        username = session.get('username')
        if not username:
            return redirect(url_for("login"))
        result = db.foods.delete_many({"name": food_name, "weekday": weekday, "time_in_day": time_in_day, "username": username})
        return redirect(url_for("home"))

    @app.route('/groceryDisplay/<path:filename>')
    def grocery_display_static(filename):
        return send_from_directory('groceryDisplay', filename)
    @app.errorhandler(Exception)
    def handle_error(e):
        """
        Output any errors - good for debugging.
        Args:
            e (Exception): The exception object.
        Returns:
            JSON response or HTML template with error message.
        """
        # Handle JSON API requests
        if request.headers.get('Content-Type') == 'application/json' or request.args.get('format') == 'json':
            return jsonify({"error": str(e)}), 500

    @app.errorhandler(Exception)
    def handle_error(e):
        return str(e), 500
    return app


app = create_app()

# Simple login routes (defined after app creation)
@app.route("/login")
def login():
    """Login page for user selection"""
    users = [u["username"] for u in app.db.users.find({}, {"username": 1, "_id": 0})]
    return render_template("login.html", users=users)
@app.route("/create_user", methods=["POST"])
def create_user():
    """Create a new user account"""
    username = request.form.get("username", "").strip()
    if not username:
        return redirect(url_for("login"))
    # Check if username already exists
    existing_user = app.db.users.find_one({"username": username})
    if existing_user:
        # User exists, just login
        session['username'] = username
        return redirect(url_for("home"))
    # Create new user
    app.db.users.insert_one({
        "username": username,
        "created_at": datetime.datetime.utcnow()
    })
    session['username'] = username
    return redirect(url_for("home"))

@app.route("/login_user", methods=["POST"])
def login_user():
    """Login with existing user"""
    username = request.form.get("username", "").strip()
    if not username:
        return redirect(url_for("login"))
    # Verify user exists
    user = app.db.users.find_one({"username": username})
    if user:
        session['username'] = username
        return redirect(url_for("home"))
    return redirect(url_for("login"))

@app.route("/get_users")
def get_users():
    """Get list of all usernames for the login page"""
    users = list(app.db.users.find({}, {"username": 1, "_id": 0}))
    usernames = [user["username"] for user in users]
    return jsonify({"users": usernames})

@app.route("/logout")
def logout():
    """Logout current user"""
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    FLASK_PORT = int(os.getenv("FLASK_PORT", "3000"))
    FLASK_ENV = os.getenv("FLASK_ENV")
    print(f"FLASK_ENV: {FLASK_ENV}, FLASK_PORT: {FLASK_PORT}")

    app.run(port=FLASK_PORT, debug=True)