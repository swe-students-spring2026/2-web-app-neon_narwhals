import os
import re
from datetime import datetime, timezone
from typing import Any

import pymongo
from dotenv import load_dotenv
# from grocery import current_list

load_dotenv()

cxn = pymongo.MongoClient(os.getenv("MONGO_URI"))
food_db = cxn[os.getenv("MONGO_DBNAME")]
current_list = food_db["current_list"]


DAYS: list[str] = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

CALORIE_GOALS: dict[str, float] = {
    "Breakfast": 450,
    "Lunch": 650,
    "Dinner": 650,
}

MEAL_COMPOSITION: dict[str, dict[str, int]] = {
    "Breakfast": {
        "Fruit": 1,
        "Dairy": 1,
        "Protein": 1,
    },
    "Lunch": {
        "Protein": 1,
        "Vegetable": 2,
        "Grain": 1,
        "Fruit": 1,
        "Dairy": 1,
    },
    "Dinner": {
        "Protein": 1,
        "Vegetable": 2,
        "Grain": 1,
        "Fruit": 1,
        "Dairy": 1,
    },
}

MEAL_CALORIE_SPLITS: dict[str, dict[str, float]] = {
    "Breakfast": {
        "Protein": 0.35,
        "Dairy": 0.40,
        "Fruit": 0.25,
    },
    "Lunch": {
        "Protein": 0.35,
        "Vegetable": 0.30,
        "Grain": 0.25,
        "Fruit": 0.05,
        "Dairy": 0.05,
    },
    "Dinner": {
        "Protein": 0.35,
        "Vegetable": 0.30,
        "Grain": 0.25,
        "Fruit": 0.05,
        "Dairy": 0.05,
    },
}


def search_food_data(food_name):
    """function for searching food information"""
    doc = food_db.foodstats.find_one({"Name": {"$regex": food_name, "$options": "i"}})
    if doc:
        doc["_id"] = str(doc["_id"])
        return doc
    else:
        return None


def lookup_food_category(food_name):
    """function for finding the category of the food"""
    doc = food_db.foodstats.find_one({"name": {"$regex": food_name, "$options": "i"}})
    # doc = food_db.foodstats.find({"Name": {"$regex": food_name}})
    if doc:
        print(doc["Category"])
        return doc["Category"]
    else:
        return None


def find_calories_per_serving(food_name):
    """find the number of calories per serving"""
    doc = food_db.foodstats.find_one({"Name": {"$regex": food_name, "$options": "i"}})

    if doc:
        return doc["Calories"] / 100
    else:
        return None


def parse_grams(amount: Any) -> float:
    match = re.search(r"[\d.]+", str(amount))
    return float(match.group()) if match else 0.0


def get_usda_record(food_name: str) -> dict[str, Any] | None:
    return food_db.foodstats.find_one({"Name": {"$regex": food_name, "$options": "i"}})



def get_calories_per_gram(food_name: str) -> float:
    record = get_usda_record(food_name)
    if record and record.get("Calories") is not None:
        return record["Calories"] / 100.0
    return 0.0


def get_food_category(food_name: str) -> str:
    record = get_usda_record(food_name)
    if record:
        return record.get("Category", "Unknown")
    return "Unknown"


def build_food_pool(grocery_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pool: list[dict[str, Any]] = []
    for item in grocery_items:
        name = item["name"]
        cal_per_gram = get_calories_per_gram(name)
        total_grams = parse_grams(item["amount"])
        pool.append(
            {
                "foodName": name,
                "foodCategory": get_food_category(name),
                "isBreakfast": item.get("time_in_day", "").lower() == "breakfast",
                "remaining_grams": total_grams,
                "cal_per_gram": cal_per_gram,
                "remaining_calories": cal_per_gram * total_grams,
            }
        )
    return pool


def fill_meal_slot(
    pool: list[dict[str, Any]],
    meal_name: str,
    calorie_goal: float,
    used_protein_today: set[str],
) -> tuple[list[dict[str, Any]], float]:
    is_breakfast = meal_name == "Breakfast"
    composition = MEAL_COMPOSITION[meal_name]
    splits = MEAL_CALORIE_SPLITS[meal_name]

    cat_budget: dict[str, float] = {
        cat: calorie_goal * splits[cat] for cat in composition
    }

    selected: list[dict[str, Any]] = []
    total_used = 0.0

    for category, quota in composition.items():
        budget = cat_budget[category]
        items_used = 0

        candidates = [f for f in pool if f["foodCategory"] == category and f["isBreakfast"] == is_breakfast and f["remaining_grams"] > 0 and f["cal_per_gram"] > 0]

        candidates.sort(key=lambda f: f["remaining_calories"], reverse=True)

        for food in candidates:
            if budget <= 0 or items_used >= quota:
                break

            max_grams_by_calories = budget / food["cal_per_gram"]
            grams_used = min(food["remaining_grams"], max_grams_by_calories)

            if grams_used < 0.1:
                continue

            calories_used = grams_used * food["cal_per_gram"]

            selected.append(
                {
                    "foodName": food["foodName"],
                    "foodCategory": category,
                    "grams": int(round(grams_used)),
                    "calories": round(calories_used, 1),
                }
            )

            food["remaining_grams"] -= grams_used
            food["remaining_calories"] -= calories_used
            budget -= calories_used
            total_used += calories_used
            items_used += 1

            if category == "Protein Foods":
                used_protein_today.add(food["foodName"])

    return selected, round(total_used, 1)


def build_meal_plan(user_id: str) -> dict[str, Any]:
    grocery_items = list(current_list.find({"username": user_id}))
    if not grocery_items:
        return {}

    pool = build_food_pool(grocery_items)
    weekly_plan: dict[str, Any] = {}

    for day in DAYS:
        daily_plan: dict[str, Any] = {}
        used_protein_today: set[str] = set()

        for meal in ("Breakfast", "Lunch", "Dinner"):
            goal = CALORIE_GOALS[meal]
            items, total_cal = fill_meal_slot(pool, meal, goal, used_protein_today)
            daily_plan[meal] = {
                "items": items,
                "total_calories": total_cal,
                "calorie_goal": goal,
            }

        weekly_plan[day] = daily_plan

    push_weekly_plan(user_id, weekly_plan)
    return weekly_plan


def push_weekly_plan(user_id: str, plan: dict[str, Any]) -> None:
    food_db.weeklymeals.update_one(
        {"username": user_id},
        {
            "$set": {
                "plan": plan,
                "updated_at": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )


def dry_run(grocery_items: list[dict[str, Any]]) -> dict[str, Any]:
    STUB_USDA: dict[str, dict[str, Any]] = {
        "beef": {"cal_per_gram": 2.50, "category": "Protein Foods"},
        "milk": {"cal_per_gram": 0.61, "category": "Dairy"},
        "broccoli": {"cal_per_gram": 0.34, "category": "Vegetables"},
        "fish": {"cal_per_gram": 2.06, "category": "Protein Foods"},
        "apples": {"cal_per_gram": 0.52, "category": "Fruits"},
        "rice": {"cal_per_gram": 1.30, "category": "Grains"},
    }

    pool: list[dict[str, Any]] = []
    for item in grocery_items:
        key = item["name"].lower()
        stub = STUB_USDA.get(key, {"cal_per_gram": 1.0, "category": "Unknown"})
        cpg = stub["cal_per_gram"]
        grams = parse_grams(item["amount"])
        pool.append(
            {
                "foodName": item["name"],
                "foodCategory": stub["category"],
                "isBreakfast": bool(item.get("breakfast", False)),
                "remaining_grams": grams,
                "cal_per_gram": cpg,
                "remaining_calories": cpg * grams,
            }
        )

    weekly_plan: dict[str, Any] = {}
    for day in DAYS:
        daily_plan: dict[str, Any] = {}
        used_protein_today: set[str] = set()

        for meal in ("Breakfast", "Lunch", "Dinner"):
            goal = CALORIE_GOALS[meal]
            items, total = fill_meal_slot(pool, meal, goal, used_protein_today)
            daily_plan[meal] = {
                "items": items,
                "total_calories": total,
                "calorie_goal": goal,
            }

        weekly_plan[day] = daily_plan

    return weekly_plan


if __name__ == "__main__":
    sample = [
        {"name": "Beef", "amount": "500", "breakfast": False},
        {"name": "Milk", "amount": "1000", "breakfast": True},
        {"name": "Broccoli", "amount": "500", "breakfast": False},
        {"name": "Fish", "amount": "500", "breakfast": False},
        {"name": "Apples", "amount": "200", "breakfast": True},
        {"name": "Rice", "amount": "700", "breakfast": False},
    ]

    print("=== Dry-run with sample grocery list ===\n")
    plan = dry_run(sample)

    for day, meals in plan.items():
        print(f"── {day} ──")
        for meal_name, data in meals.items():
            print(f"  {meal_name}  (goal: {data['calorie_goal']} kcal | used: {data['total_calories']} kcal)")
            for it in data["items"]:
                print(f"    • {it['foodName']:12s}  {it['grams']:6d} g  = {it['calories']:6.1f} kcal  [{it['foodCategory']}]")
        print()
