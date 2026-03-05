from __future__ import annotations
import os
import re
from datetime import datetime, timezone
from typing import Any

import pymongo
from dotenv import load_dotenv

load_dotenv()

cxn = pymongo.MongoClient(os.getenv("MONGO_URI"))
food_db = cxn[os.getenv("MONGO_DBNAME")]


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
    doc = food_db.foodstats.find_one({"Name": {"$regex": food_name, "$options": "i"}})
    if doc:
        doc["_id"] = str(doc["_id"])
        return doc
    return None


def lookup_food_category(food_name):
    doc = food_db.foodstats.find_one({"name": {"$regex": food_name, "$options": "i"}})
    if doc:
        return doc["Category"]
    return None


def find_calories_per_serving(food_name):
    doc = food_db.foodstats.find_one({"Name": {"$regex": food_name, "$options": "i"}})
    if doc:
        return doc["Calories"] / 100
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
        total_grams = parse_grams(item.get("amount", 0))
        total_calories = float(item.get("calories", 0))
        cal_per_gram = (total_calories / total_grams) if total_grams > 0 else 0.0
        pool.append(
            {
                "_db_id": item["_id"],
                "foodName": name,
                "foodCategory": item.get("food_type", "Unknown"),
                "isBreakfast": item.get("time_in_day", "").lower() == "breakfast",
                "original_grams": total_grams,
                "remaining_grams": total_grams,
                "cal_per_gram": cal_per_gram,
                "remaining_calories": total_calories,
            }
        )
    return pool


def update_current_list_amounts(pool: list[dict[str, Any]]) -> None:
    for item in pool:
        grams_used = item["original_grams"] - item["remaining_grams"]
        if grams_used > 0:
            food_db["current_list"].update_one(
                {"_id": item["_db_id"]},
                {"$set": {"amount": str(int(round(item["remaining_grams"])))}}
            )


def restore_grams_to_current_list(
    user_id: str, food_name: str, grams: float
) -> None:
    item = food_db["current_list"].find_one({"username": user_id, "name": food_name})
    if item:
        current = parse_grams(item.get("amount", "0"))
        food_db["current_list"].update_one(
            {"_id": item["_id"]},
            {"$set": {"amount": str(int(round(current + grams)))}}
        )


def fill_meal_slot(
    pool: list[dict[str, Any]],
    meal_name: str,
    calorie_goal: float,
    used_protein_today: set[str],
) -> tuple[list[dict[str, Any]], float, list[str]]:
    is_breakfast = meal_name == "Breakfast"
    composition = MEAL_COMPOSITION[meal_name]
    splits = MEAL_CALORIE_SPLITS[meal_name]

    cat_budget: dict[str, float] = {
        cat: calorie_goal * splits[cat] for cat in composition
    }

    selected: list[dict[str, Any]] = []
    total_used = 0.0
    missing_categories: list[str] = []

    for category, quota in composition.items():
        budget = cat_budget[category]
        items_used = 0

        candidates = [
            f for f in pool
            if f["foodCategory"] == category
            and f["isBreakfast"] == is_breakfast
            and f["remaining_grams"] > 0
            and f["cal_per_gram"] > 0
        ]

        if not candidates:
            missing_categories.append(category)
            continue

        candidates.sort(key=lambda f: f["remaining_grams"], reverse=True)

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

    return selected, round(total_used, 1), missing_categories


def build_meal_plan(user_id: str) -> dict[str, Any]:
    grocery_items = list(food_db["current_list"].find({"username": user_id}))
    if not grocery_items:
        return {}

    pool = build_food_pool(grocery_items)
    weekly_plan: dict[str, Any] = {}
    all_missing: set[str] = set()

    for day in DAYS:
        daily_plan: dict[str, Any] = {}
        used_protein_today: set[str] = set()

        for meal in ("Breakfast", "Lunch", "Dinner"):
            goal = CALORIE_GOALS[meal]
            items, total_cal, missing = fill_meal_slot(
                pool, meal, goal, used_protein_today)
            all_missing.update(missing)
            daily_plan[meal] = {
                "items": items,
                "total_calories": total_cal,
                "calorie_goal": goal,
            }

        weekly_plan[day] = daily_plan

    update_current_list_amounts(pool)
    push_weekly_plan(user_id, weekly_plan, sorted(all_missing))
    return {"plan": weekly_plan, "missing_categories": sorted(all_missing)}


def push_weekly_plan(
    user_id: str, plan: dict[str, Any], missing_categories: list[str]
) -> None:
    food_db.weeklymeals.update_one(
        {"username": user_id},
        {
            "$set": {
                "plan": plan,
                "missing_categories": missing_categories,
                "updated_at": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )


if __name__ == "__main__":
    usernames = food_db["current_list"].distinct("username")
    if not usernames:
        print("No users found in foods collection.")
    for username in usernames:
        print(f"=== Generating meal plan for: {username} ===")
        result = build_meal_plan(username)
        if not result:
            print(f"  No food items found for {username}\n")
            continue
        if result["missing_categories"]:
            print(f"  WARNING - Missing categories: {result['missing_categories']}")
        plan = result["plan"]
        for day, meals in plan.items():
            print(f"\n  -- {day} --")
            for meal_name, data in meals.items():
                print(
                    f"    {meal_name}: {data['total_calories']} / "
                    f"{data['calorie_goal']} kcal"
                )
                for it in data["items"]:
                    print(
                        f"      • {it['foodName']:20s} {it['grams']:5d}g"
                        f"  {it['calories']:6.1f} kcal  [{it['foodCategory']}]"
                    )
        print()
    print("weeklymeals updated for:", food_db.weeklymeals.distinct("username"))