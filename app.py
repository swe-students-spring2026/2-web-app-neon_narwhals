#!/usr/bin/env python3

"""
Example flask-based web application.
See the README.md file for instructions how to set up and run the app in development mode.
"""

import os
import datetime
#from flask import Flask, render_template, request, redirect, url_for
from flask import Flask, render_template, request, redirect, url_for, jsonify
import pymongo
from bson.objectid import ObjectId
from dotenv import load_dotenv, dotenv_values

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

    @app.route("/")
    def home():
        """
        Route for the home page - displays all food items in HTML or returns JSON.
        Returns:
            HTML template or JSON response with all food items.
        """
        food_docs = list(db.foods.find({}).sort("created_at", -1))
        
        # Check if request wants JSON (API usage)
        if request.headers.get('Content-Type') == 'application/json' or request.args.get('format') == 'json':
            # Convert ObjectId to string for JSON serialization
            for doc in food_docs:
                doc['_id'] = str(doc['_id'])
            return jsonify({"foods": food_docs})
        
        # Return HTML template for web interface
        return render_template("index.html", foods=food_docs)

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
                return render_template("error.html", error="Food item not found"), 404
        
        # Handle JSON API requests
        if request.headers.get('Content-Type') == 'application/json' or request.args.get('format') == 'json':
            food_doc['_id'] = str(food_doc['_id'])
            return jsonify({"food": food_doc})
        
        # Return HTML template for web interface
        return render_template("edit.html", food=food_doc)

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
                return redirect(url_for("home"))
            else:
                return render_template("error.html", error="Food item not found"), 404

    @app.route("/delete/<food_id>")
    def delete(food_id):
        """
        Route for DELETE/GET requests to delete a food item.
        Deletes the specified food record from the database.
        Args:
            food_id (str): The ID of the food item to delete.
        Returns:
            JSON response or redirect to home page.
        """
        result = db.foods.delete_one({"_id": ObjectId(food_id)})
        
        # Handle JSON API requests
        if request.headers.get('Content-Type') == 'application/json' or request.args.get('format') == 'json':
            if result.deleted_count > 0:
                return jsonify({"message": "Food deleted successfully"})
            else:
                return jsonify({"error": "Food item not found"}), 404
        
        # Handle HTML requests - redirect to home page
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

    @app.route("/search_database/<food_name>")
    def search_food_data(food_name):
        doc = db.foodstats.find_one({"Name": {"$regex": food_name, "$options": "i"}})
        if doc:
            doc["_id"] = str(doc["_id"])
            return doc
        else:
            return jsonify({"error": "Food not found"}), 404

    @app.route("/search_database/<food_name>/category")
    def lookup_food_category(food_name):
        doc = db.foodstats.find_one({"Name": {"$regex": food_name, "$options": "i"}})
        if doc:
            return doc["Category"]
        else:
            return jsonify({"error": "Food not found"}), 404
    @app.route("/search_database/calorie_limit/<cal_limit>")
    def lookup_calories_limit(cal_limit):
        docs = list(db.foodstats.find({"Cal_per_serv": {"$lte": float(cal_limit)}}))
        if docs:
            for doc in docs:
                doc["_id"] = str(doc["_id"])
            return jsonify({"foods": docs})
        else:
            return jsonify({"error": "No food found for calorie limit"}), 404

    


    

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
        
        # Handle HTML requests
        return render_template("error.html", error=str(e)), 500

    return app


app = create_app()

if __name__ == "__main__":
    FLASK_PORT = int(os.getenv("FLASK_PORT", "3000"))
    FLASK_ENV = os.getenv("FLASK_ENV")
    print(f"FLASK_ENV: {FLASK_ENV}, FLASK_PORT: {FLASK_PORT}")

    app.run(port=FLASK_PORT)
