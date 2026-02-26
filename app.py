#!/usr/bin/env python3

"""
Example flask-based web application.
See the README.md file for instructions how to set up and run the app in development mode.
"""

import os
import datetime
#from flask import Flask, render_template, request, redirect, url_for
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory, Blueprint
import pymongo
from bson.objectid import ObjectId
from dotenv import load_dotenv, dotenv_values
from grocery import grocery_bp
# from jinja2 import ChoiceLoader, FileSystemLoader


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

    app = Flask(__name__, template_folder='weeklyDisplay')
    
    # load flask config from env variables
    config = dotenv_values()
    app.config.from_mapping(config)

    cxn = pymongo.MongoClient(os.getenv("MONGO_URI"))
    db = cxn[os.getenv("MONGO_DBNAME")]

    try:
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
    
    # @app.route("/grocery-list")
    # def grocery_list():
    #     """Grocery list page from groceryDisplay folder"""
    #     return send_from_directory('groceryDisplay', 'grocery-list.html')

    # @app.route("/groceryDisplay/<path:filename>")
    # def serve_grocery_display(filename):
    #     """ CSS, images, and other assets from groceryDisplay folder."""
    #     return send_from_directory('groceryDisplay', filename)

    @app.route("/")
    @app.route("/week")
    def home():
        """
        Route for the home page - displays weekly food view.
        Returns:
            HTML template or JSON response with weekly food data.
        """
        food_docs = list(db.foods.find({}).sort("created_at", -1))
        
        # Check if request wants JSON (API usage)
        if request.headers.get('Content-Type') == 'application/json' or request.args.get('format') == 'json':
            # Convert ObjectId to string for JSON serialization
            for doc in food_docs:
                doc['_id'] = str(doc['_id'])
            return jsonify({"foods": food_docs})
        
        # Organize foods by weekday and meal time for weekly view
        week_days = []
        weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        weekday_display = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        
        # Get current day for highlighting
        import datetime
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

    @app.route("/day/<weekday>")
    def day_view(weekday):
        """
        Route for individual day view for adding/editing meals.
        Args:
            weekday (str): The weekday to display
        Returns:
            HTML template with day-specific food form
        """
        # Get foods for this specific day
        day_foods = list(db.foods.find({"weekday": weekday.lower()}).sort("created_at", -1))
        
        # Organize by meal time
        meals = {
            'breakfast': [food for food in day_foods if food.get('time_in_day', '').lower() == 'breakfast'],
            'lunch': [food for food in day_foods if food.get('time_in_day', '').lower() == 'lunch'],
            'dinner': [food for food in day_foods if food.get('time_in_day', '').lower() == 'dinner']
        }
        
        # Calculate basic summary (simplified for now)
        total_calories = sum(food.get('calorie_amount', 0) for food in day_foods)
        total_protein = sum(food.get('food_amount', 0) for food in day_foods if food.get('food_type') == 'protein')
        
        # Day navigation
        weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        current_index = weekdays.index(weekday.lower()) if weekday.lower() in weekdays else 0
        prev_weekday = weekdays[(current_index - 1) % 7]
        next_weekday = weekdays[(current_index + 1) % 7]
        
        import datetime
        weekday_display = weekday.title()
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
        db.foods.delete_many({"weekday": weekday.lower()})
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
        db.foods.delete_many({"weekday": weekday.lower(), "time_in_day": meal.lower()})
        return redirect(url_for("day_view", weekday=weekday))

    @app.route("/swap-day/<weekday>", methods=["POST"])
    def swap_day(weekday):
        """
        Route to swap meals within a day (placeholder functionality).
        Args:
            weekday (str): The weekday to swap
        Returns:
            Redirect to day view
        """
        # Placeholder - could implement meal swapping logic here
        return redirect(url_for("day_view", weekday=weekday))

    @app.route("/delete-week", methods=["POST"])
    def delete_week():
        """
        Route to delete all meals for the entire week.
        Returns:
            Redirect to home page
        """
        db.foods.delete_many({})
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
            
            result = db.foods.insert_one(food.to_dict())
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
            db.foods.insert_one(food.to_dict())

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
        food_doc = db.foods.find_one({"_id": ObjectId(food_id)})
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

            result = db.foods.update_one({"_id": ObjectId(food_id)}, {"$set": updated_food})
            
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

            result = db.foods.update_one({"_id": ObjectId(food_id)}, {"$set": updated_food})
            
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
        # Get the food item first to know which day to redirect to
        food_doc = db.foods.find_one({"_id": ObjectId(food_id)})
        weekday = food_doc.get('weekday', 'monday') if food_doc else 'monday'
        
        result = db.foods.delete_one({"_id": ObjectId(food_id)})
        
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

    @app.route("/delete-by-content/<food_name>/<weekday>/<time_in_day>", methods=["DELETE"])
    def delete_by_content(food_name, weekday, time_in_day):
        """
        Route for DELETE requests to delete food items by their name, weekday, and time.
        Deletes the specified food records from the database.
        Args:
            food_name (str): The name of the food item.
            weekday (str): The weekday of the food item.
            time_in_day (str): The time in day of the food item.
        Returns:
            JSON response with success message and count of deleted items.
        """
        result = db.foods.delete_many({"name": food_name, "weekday": weekday, "time_in_day": time_in_day})
        return jsonify({"message": f"Deleted {result.deleted_count} food items"})

    @app.route('/groceryDisplay/<path:filename>')
    def grocery_display_static(filename):
        return send_from_directory('groceryDisplay', filename)
        
    @app.route("/search_database/<food_name>")
    def search_food_data(food_name):
        doc = db.foodstats.find_one({"Name":{"$regex": food_name, "$options":"i"}})
        if doc:
            doc["_id"] = str(doc["_id"])
            return jsonify(doc)
        else:
            return jsonify ({"error": "Food not found"}), 404

    @app.route("/search_database/<food_name>/category")
    def lookup_food_category(food_name):
        doc = db.foodstats.find_one({"Name": {"$regex": food_name, "$options": "i"}})
        if doc:
            return doc["Category"]
        else:
            return jsonify ({"error": "Food not found"}), 404
    @app.route("/search_database/<food_name>/find_calperserv")
    def find_calories_per_serving(food_name):
        doc = db.foodstats.find_one({"Name":{"$regex": food_name, "$options": "i"}})
        if doc:
            return jsonify(doc["Calories"]/100)
        else:
            return jsonify ({"error": "Food not found"}), 404
    
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

if __name__ == "__main__":
    FLASK_PORT = int(os.getenv("FLASK_PORT", "3000"))
    FLASK_ENV = os.getenv("FLASK_ENV")
    print(f"FLASK_ENV: {FLASK_ENV}, FLASK_PORT: {FLASK_PORT}")

    app.run(port=FLASK_PORT, debug=True)
