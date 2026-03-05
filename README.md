# Web Application Exercise

A little exercise to build a web application following an agile development process. See the [instructions](instructions.md) for more detail.

## Product vision statement

Our meal prepping website allows users to conveniently organize their groceries into planned meals and simplify the meal prepping process. 

## User stories

[Link](https://github.com/swe-students-spring2026/2-web-app-neon_narwhals/issues/3#issue-3955535770)

## Steps necessary to run the software

Below are end‑to‑end steps to get the project running on a new machine.

### Prerequisites

- **Python** 3.10 or newer installed 
- **Git**
- **MongoDB** running locally (e.g. `mongodb://localhost:27017`)

### Clone the repository

```bash
git clone https://github.com/swe-students-spring2026/2-web-app-neon_narwhals.git
cd 2-web-app-neon_narwhals
```

If you are using SSH, clone with the SSH URL instead.

### Install dependencies and create environment


**Using pipenv:**

```bash
pip3 install pipenv
pipenv install -r requirements.txt
```

This creates a virtual environment and installs all dependencies from `requirements.txt`. 

###  Configure environment variables (`.env`)

Our app reads its configuration from a `.env` file in the project root.

1. Start from the example file:

   ```bash
   cp env.example .env   # macOS / Linux
   # or
   copy env.example .env  # Windows (PowerShell / CMD)
   ```

2. Open `.env` in a text editor and set at least:

   ```env
   # Local MongoDB example
   MONGO_URI=mongodb://localhost:27017
   MONGO_DBNAME=mealprep

   # You can also optionally set port and environment for Flask
   # FLASK_PORT=3000
   # FLASK_ENV=development
   ```


###  Start MongoDB

Make sure MongoDB server is running before starting Flask:

- **Local MongoDB** – start the MongoDB service (e.g. `mongod` or via your OS service manager).

###  Run the Flask app

From the project root...


```bash
pipenv run python app.py
```


Output should look like something like this...

```text
FLASK_ENV: None, FLASK_PORT: 3000
 * Serving Flask app "app"
 * Running on http://127.0.0.1:3000/ (Press CTRL+C to quit)
```

###  Open the application in a browser

Open browser of choice, you can navigate to the following pages via these links or from nav bar...

- **Week view:** `http://127.0.0.1:3000/week`
- **Day view (breakfast / lunch / dinner):** `http://127.0.0.1:3000/day`
- **Grocery list (current list with categories and add form):** `http://127.0.0.1:3000/grocery-list`
- **Grocery history:** `http://127.0.0.1:3000/grocery-history`

> If the app redirects you to a login screen, create a user 

### Using app

Once the server is running and pages load without errors, interact with our app!

- **Add / edit / delete meals:**

  - Use the Grocery tab to add items, Day and Week views to edit items, and delete either individual meals or whole days.
- **Swap days in Week view:**
  - On week view use the **↑ / ↓** arrows in each day header to swap all meals for that day with the day above/below.
- **Swap meals within a day:**
  - On day view use the small **↑ / ↓** arrows in the Breakfast/Lunch/Dinner headers to move a whole meal block up or down (e.g. swap Lunch with Dinner).
- **Grocery list & history:**
  - Visit `/grocery-list` to see the grocery layout and `/grocery-history` to see the history mock‑up. These screens share the same bottom navigation as the Home/Week/Day views.
- **Algorithm**
  -Our algorithm allocates the groceries inserted by user in grocery list evenly throughout the week. Making sure user reaches nutritional goals


## Task boards

[Link for Sprint 1](https://github.com/orgs/swe-students-spring2026/projects/11/views/2)

[Link for Sprint 2](https://github.com/orgs/swe-students-spring2026/projects/60/views/2)
