# Setup instructions

1. `cd` to `app`

2. Create a virtual environment: `python -m venv venv`

3. Activate the virtual environment (Windows: `.\venv\Scripts\activate`)

4. Create a Postgres database with the schema provided in `schema.sql`

5. Create a `config.txt` with the following content (replace as needed):

```
[Database Config]
DB_HOST = localhost
DB_NAME = your_db_name
DB_USER = your_db_user
DB_PASS = your_db_pass
[Photos Config]
PHOTOS_FOLDER = photos
[User Config]
GUEST_USER_ID = -1
```

6. Run the application once (see Run instructions)

7. Create a user with first name 'Guest' and last name 'User'

8. Edit `config.txt` and set `GUEST_USER_ID` with the ID of the created Guest user

# Run instructions

0. Enter the virtual environment

1. In the `app` directory, do `python app.py`

2. Go to `http://localhost:5000/` in your browser
