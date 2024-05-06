from flask import Flask, render_template, request, flash, redirect, url_for, session, g
import psycopg2
import psycopg2.extras
from psycopg2.extras import DictRow
import configparser
import os
import uuid
import re

# Read confir from file
config = configparser.RawConfigParser()
config.read('config.txt')

# Initiate Postgres connection
connection = psycopg2.connect(
    host = config.get('Database Config', 'DB_HOST'),
    dbname = config.get('Database Config', 'DB_NAME'),
    user = config.get('Database Config', 'DB_USER'),
    password = config.get('Database Config', 'DB_PASS')
)

# Create photos directory in the static directory if it does not exist
photos_dir = config.get('Photos Config', 'PHOTOS_FOLDER')
os.makedirs(os.path.join('static', photos_dir), exist_ok=True)

# Start the app
app = Flask(__name__)
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/' # In a real situation, should be read from a private config file

guest_user_id = config.get('User Config', 'GUEST_USER_ID')

def get_extension(filename: str) -> str | None:
    if '.' not in filename:
        return None
    
    parts = filename.split('.')
    if len(parts) < 2:
        return None
    
    return parts[-1].lower()

def is_filename_image(filename: str) -> bool:
    extension = get_extension(filename)
    return extension is not None and extension in ['jpg', 'jpeg', 'png']

def get_photo_filename_path(filename: str) -> str:
    return f'static/{photos_dir}/{filename}'

def get_photo_url(photo) -> str:
    return get_photo_filename_url(photo['filename'])

def get_photo_filename_url(filename: str) -> str:
    filename_in_photos_dir = f'{photos_dir}/{filename}'
    return url_for('static', filename=filename_in_photos_dir)

def get_user_by_login(email: str, password: str) -> DictRow | None:
    # Credits: https://www.psycopg.org/docs/extras.html
    dict_cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    dict_cursor.execute('select u.user_id, u.first_name, u.last_name from users u where u.email = %s and u.password = %s', (email, password))
    user = dict_cursor.fetchone()
    dict_cursor.close()
    return user

def get_user_by_user_id(user_id: int) -> DictRow | None:
    dict_cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    dict_cursor.execute('select u.user_id, u.first_name, u.last_name from users u where u.user_id = %s', (user_id, ))
    user = dict_cursor.fetchone()
    dict_cursor.close()
    return user

def get_top_users(user_count: int) -> list[DictRow]:
    dict_cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    dict_cursor.execute("""
        select u.user_id, u.first_name, u.last_name, (user_comments_count.comment_count + user_photo_count.photo_count) as score
        from (
            select u.user_id, coalesce(count(comment_id), 0) as comment_count
            from users u
            left join comments c on c.user_id = u.user_id
            group by u.user_id
        ) user_comments_count
        join
        (
            select u.user_id, coalesce(count(photo_id), 0) as photo_count
            from users u
            left join albums a on a.owner_id = u.user_id
            left join photos p on p.album_id = a.album_id
            group by u.user_id
        ) user_photo_count on user_comments_count.user_id = user_photo_count.user_id
        join users u on u.user_id = user_comments_count.user_id
        where u.user_id != %s
        order by score desc
        limit %s
    """, (guest_user_id, user_count, ))
    users = dict_cursor.fetchall()
    dict_cursor.close()
    return users

def add_user(first_name, last_name, hometown, gender, email, birth_date, password) -> bool:
    error = None
    cursor = connection.cursor()
    
    try:
        if len(birth_date) > 0:
            cursor.execute("""
                insert into users (first_name, last_name, hometown, gender, email, birth_date, password)
                values (%s, %s, %s, %s, %s, %s, %s)
            """, (first_name, last_name, hometown, gender, email, birth_date, password))
        else:
            cursor.execute("""
                insert into users (first_name, last_name, hometown, gender, email, password)
                values (%s, %s, %s, %s, %s, %s)
            """, (first_name, last_name, hometown, gender, email, password))    
    except psycopg2.errors.UniqueViolation:
        error = 'That email is already in use. Please try again.'
    except psycopg2.errors.CheckViolation:
        error = 'Your password must be at least 10 characters. Please try again.'
    except Exception as e:
        error = f'An error occurred. Please try again later. Error: {e}'

    connection.commit()
    cursor.close()
    
    if error is not None:
        flash(error)
        return False
    
    return True

def add_album(album_name: str, owner_id: int) -> bool:
    cursor = connection.cursor()
    error = None

    try:
        cursor.execute("""
            insert into albums (name, creation_date, owner_id)
            values (%s, now(), %s)
        """, (album_name, owner_id))
    except Exception as e:
        error = f'An error occurred. Please try again later. Error: {e}'

    connection.commit()
    cursor.close()

    if error is not None:
        flash(error)
        return False

    return True

def get_album_by_album_id(album_id: int) -> DictRow | None:
    dict_cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    dict_cursor.execute('select * from albums a where a.album_id = %s', (album_id, ))
    album = dict_cursor.fetchone()
    dict_cursor.close()
    return album

def get_albums_by_owner_id(owner_id: int) -> list[DictRow]:
    dict_cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    dict_cursor.execute("""
        select *, u.first_name as owner_first_name, u.last_name as owner_last_name
        from albums a
        join users u on u.user_id = a.owner_id
        where a.owner_id = %s
    """, (owner_id, ))
    albums = dict_cursor.fetchall()
    dict_cursor.close()
    return albums

def get_all_albums() -> list[DictRow]:
    dict_cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    dict_cursor.execute("""
        select *, u.first_name as owner_first_name, u.last_name as owner_last_name
        from albums a
        join users u on u.user_id = a.owner_id
    """)
    albums = dict_cursor.fetchall()
    dict_cursor.close()
    return albums

def get_photo_album_owner_id(photo_id: int) -> int:
    dict_cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    dict_cursor.execute("""
        select a.owner_id as owner_id
        from albums a
        join photos p on p.album_id = a.album_id
        where p.photo_id = %s
    """, (photo_id, ))
    album = dict_cursor.fetchone()
    dict_cursor.close()
    return album['owner_id']

def add_photo(caption, filename, album_id) -> int | None:
    cursor = connection.cursor()
    error = None

    # Add the photo
    # Get the photo id
    # Partial credits: https://stackoverflow.com/a/2944481/4580269
    try:
        cursor.execute("""
            insert into photos (caption, filename, album_id)
            values (%s, %s, %s)
            returning photo_id
        """, (caption, filename, album_id))
    except Exception as e:
        error = f'An error occurred. Please try again later. Error: {e}'

    connection.commit()
    
    if error is not None:
        cursor.close()
        flash(error)
        return None
    
    photo_id = cursor.fetchone()
    cursor.close()
    return photo_id

def get_photos_by_album_id(album_id: int) -> list[DictRow]:
    dict_cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    dict_cursor.execute('select * from photos p where p.album_id = %s', (album_id, ))
    photos = dict_cursor.fetchall()
    dict_cursor.close()
    return photos

def get_photo_filename_by_photo_id(photo_id: int) -> str | None:
    cursor = connection.cursor()
    cursor.execute('select filename from photos p where p.photo_id = %s', (photo_id, ))
    tuple = cursor.fetchone()
    cursor.close()
    if tuple is None:
        return None
    filename = tuple[0]
    return filename

def is_photo_in_album(photo_id: int, album_id: int) -> bool:
    cursor = connection.cursor()
    cursor.execute('select p.album_id from photos p where p.photo_id = %s', (photo_id, ))
    tuple = cursor.fetchone()
    cursor.close()
    return tuple is not None and tuple[0] == album_id

def get_friend_status(user1_id: int, user2_id: int) -> bool:
    cursor = connection.cursor()
    cursor.execute('select count(*) from friends where user1_id = %s and user2_id = %s', (user1_id, user2_id))
    tuple = cursor.fetchone()
    cursor.close()
    return tuple[0] == 1

def add_friend(user1_id: int, user2_id: int) -> None:
    cursor = connection.cursor()
    cursor.execute('insert into friends (user1_id, user2_id) values (%s, %s)', (user1_id, user2_id))
    connection.commit()
    cursor.close()

def remove_friend(user1_id: int, user2_id: int) -> None:
    cursor = connection.cursor()
    cursor.execute('delete from friends where user1_id = %s and user2_id = %s', (user1_id, user2_id))
    connection.commit()
    cursor.close()

def get_user_friends(user_id: int) -> list[DictRow]:
    dict_cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    dict_cursor.execute("""
        select u.user_id, u.first_name, u.last_name
        from friends f
        join users u on f.user2_id = u.user_id
        where f.user1_id = %s
    """, (user_id, ))
    users = dict_cursor.fetchall()
    dict_cursor.close()
    return users

def get_non_friends_by_first_or_last_name_containing(user_id: int, query: str) -> list[DictRow]:
    dict_cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    dict_cursor.execute("""
        select u.user_id, u.first_name, u.last_name
        from users u
        where
            (lower(concat(u.first_name, ' ', u.last_name)) like lower(concat('%%', %s, '%%')))
            and u.user_id != %s
            and u.user_id not in (
                select f.user2_id
                from friends f
                where f.user1_id = %s
            )
    """, (query, user_id, user_id))
    users = dict_cursor.fetchall()
    dict_cursor.close()
    return users
 
def get_friend_recommendations(user_id: int) -> list[DictRow]:
    dict_cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    dict_cursor.execute("""
        select user_id, first_name, last_name    
        from (
            (
                select user2_id
                from (
                    select user2_id as user_id
                    from friends
                    where user1_id = %s
                ) my_friends
                join friends f on my_friends.user_id = f.user1_id
                where f.user2_id != %s
            )
            except (
                select user2_id as user_id
                from friends
                where user1_id = %s
            )
        ) friends_of_my_friends
        join users u on u.user_id = friends_of_my_friends.user2_id
        group by u.user_id
        having count(*) > 1
        order by count(*) desc
    """, (user_id, user_id, user_id ))
    users = dict_cursor.fetchall()
    dict_cursor.close()
    return users

def get_like_status(photo_id: int, user_id: int) -> bool:
    cursor = connection.cursor()
    cursor.execute('select count(*) from likes where user_id = %s and photo_id = %s', (user_id, photo_id))
    tuple = cursor.fetchone()
    cursor.close()
    return tuple[0] == 1

def like_photo(user_id: int, photo_id: int) -> None:
    cursor = connection.cursor()
    cursor.execute('insert into likes (user_id, photo_id) values (%s, %s)', (user_id, photo_id))
    connection.commit()
    cursor.close()
    
def unlike_photo(user_id: int, photo_id: int) -> None:
    cursor = connection.cursor()
    cursor.execute('delete from likes where user_id = %s and photo_id = %s', (user_id, photo_id))
    connection.commit()
    cursor.close()

def get_photo_info(photos: list[DictRow], set_album_owner_id: bool, set_like_info: bool, set_comments: bool, set_tags: bool) -> list[dict]:
    user_id = None if g.user is None else g.user['user_id']
    new_photos = []

    for photo in photos:
        photo = dict(photo)
        new_photos.append(photo)
        photo_id = photo['photo_id']

        if set_album_owner_id:
            # Set album owner id
            photo['owner_id'] = get_photo_album_owner_id(photo_id)

        if set_like_info:
            # Set like status
            photo['is_liked'] = False if user_id is None else get_like_status(photo_id, user_id)
            # Get and set users who liked
            photo['liked_users'] = get_names_of_users_who_liked_photo(photo_id)

        if set_comments:
            # Get and set comments
            photo['comments'] = get_photo_comments(photo_id)

        if set_tags:
            # Get and set tags
            photo['tag_labels'] = get_photo_tag_labels(photo_id)

    return new_photos

def get_names_of_users_who_liked_photo(photo_id: int) -> list[DictRow]:
    dict_cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    dict_cursor.execute("""
        select u.first_name, u.last_name
        from users u
        join likes l on u.user_id = l.user_id
        where l.photo_id = %s
    """, (photo_id, ))
    names = dict_cursor.fetchall()
    dict_cursor.close()
    return names

def add_comment(user_id: int, photo_id: int, text: str) -> bool:
    cursor = connection.cursor()
    error = None

    try:
        cursor.execute("""
            insert into comments (text, creation_date, photo_id, user_id)
            values (%s, now(), %s,%s)
        """, (text, photo_id, user_id))
    except Exception as e:
        error = f'An error occurred. Please try again later. Error: {e}'

    connection.commit()
    cursor.close()

    if error is not None:
        flash(error)
        return False

    return True

def get_photo_comments(photo_id: int) -> list[DictRow]:
    dict_cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    dict_cursor.execute("""
        select c.text, c.creation_date, u.first_name, u.last_name 
        from comments c
        join users u on c.user_id = u.user_id
        where c.photo_id = %s
    """, (photo_id, ))
    comments = dict_cursor.fetchall()
    dict_cursor.close()
    return comments

def get_users_by_comments_containing(query: str) -> list[DictRow]:
    dict_cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    dict_cursor.execute("""
        select u.user_id, u.first_name, u.last_name, m.match_count
        from (
            select c.user_id, count(*) as match_count
            from comments c
            where c.text like concat('%%', %s, '%%')
            group by c.user_id
        ) m
        join users u on u.user_id = m.user_id
        order by m.match_count desc
    """, (query, ))
    users = dict_cursor.fetchall()
    dict_cursor.close()
    return users

def parse_tags_string(tags_string: str) -> list[str]:
    a = tags_string.split(' ')
    a = list(set(map(lambda x: x.lower().strip(), a)))

    for x in a:
        if not re.match(r'^[a-z]+$', x):
            return None

    return a

def does_tag_exist(label: str) -> bool:
    cursor = connection.cursor()
    cursor.execute('select count(*) from tags where label = %s', (label, ))
    tuple = cursor.fetchone()
    cursor.close()
    return tuple[0] == 1

def add_tag(label: str) -> bool:
    cursor = connection.cursor()
    error = None
    
    try:
        cursor.execute('insert into tags (label) values (%s)', (label, ))
    except psycopg2.errors.UniqueViolation:
        error = 'That tag already exists. Please try again with the same tags'
    except psycopg2.errors.CheckViolation:
        error = 'Invalid tag. Please try with another tag'
    except Exception as e:
        error = f'An error occurred. Please try again later. Error: {e}'

    connection.commit()
    cursor.close()

    if error is not None:
        flash(error)
        return False

    return True

def add_photo_tag(photo_id: int, tag_label: str) -> bool:
    cursor = connection.cursor()
    error = None
    
    try:
        cursor.execute('insert into photo_tags (tag_label, photo_id) values (%s, %s)', (tag_label, photo_id))
    except Exception as e:
        error = f'An error occurred. Please try again later. Error: {e}'

    connection.commit()
    cursor.close()

    if error is not None:
        flash(error)
        return False

    return True

def get_photo_tag_labels(photo_id: int) -> list[str]:
    cursor = connection.cursor()
    cursor.execute("""
        select pt.tag_label
        from photo_tags pt
        where pt.photo_id = %s
    """, (photo_id, ))
    tuples = cursor.fetchall()
    cursor.close()
    tag_labels = list(map(lambda tuple: tuple[0], tuples))
    return tag_labels

def get_famous_tags(tag_count: int) -> list[str]:
    cursor = connection.cursor()
    cursor.execute("""
        select pt.tag_label 
        from photo_tags pt
        group by pt.tag_label
        order by count(*) desc
        limit %s
    """, (tag_count, ))
    tuples = cursor.fetchall()
    cursor.close()
    tag_labels = list(map(lambda tuple: tuple[0], tuples))
    return tag_labels

def get_all_photos_by_tags(tags: list[str]) -> list[DictRow]:
    dict_cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    dict_cursor.execute("""
        select * 
        from photos p
        where %s = (
            select count(*)
            from photo_tags pt
            where pt.photo_id = p.photo_id
            and pt.tag_label = any (%s)                
        ) 
    """, (len(tags), tags))
    photos = dict_cursor.fetchall()
    dict_cursor.close()
    return photos

def get_user_photos_by_tags(tags: list[str], user_id: int) -> list[DictRow]:
    dict_cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    dict_cursor.execute("""
        select * 
        from photos p
        join albums a on p.album_id = a.album_id
        where a.owner_id = %s 
        and %s = (
            select count(*)
            from photo_tags pt
            where pt.photo_id = p.photo_id
            and pt.tag_label = ANY (%s)                
        ) 
    """, (user_id, len(tags), tags))
    photos = dict_cursor.fetchall()
    dict_cursor.close()
    return photos

def get_recommended_photos(tag_labels: list[str], user_id: int) -> list[DictRow]:
    dict_cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    dict_cursor.execute("""
        select p.photo_id, p.caption, p.filename, p.album_id
        from (
            select pt.photo_id
            from photo_tags pt
            where pt.tag_label = any (%s)
            group by pt.photo_id
            order by count(*) desc
        ) valid_photo_ids
        join photos p on p.photo_id = valid_photo_ids.photo_id
        join photo_tags pt on pt.photo_id = valid_photo_ids.photo_id
        join albums a on a.album_id = p.album_id
        where a.owner_id != %s
        group by p.photo_id
        order by count(*) asc
    """, (tag_labels, user_id))
    photos = dict_cursor.fetchall()
    dict_cursor.close()
    return photos

def get_user_top_tags(user_id: int, tag_count: int) -> list[str]:
    dict_cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    dict_cursor.execute("""
        select pt.tag_label
        from photo_tags pt
        join photos p on p.photo_id = pt.photo_id
        join albums a on a.album_id = p.album_id
        where a.owner_id = %s
        group by pt.tag_label
        order by count(*) desc
        limit %s
    """, (user_id, tag_count))
    tuples = dict_cursor.fetchall()
    dict_cursor.close()
    tag_labels = list(map(lambda tuple: tuple[0], tuples))
    return tag_labels

@app.context_processor
def inject_functions():
    # Credits: https://flask.palletsprojects.com/en/3.0.x/templating/#context-processors
    return dict(get_photo_url=get_photo_url)

@app.before_request
def store_prev_url():
    session['prev_url'] = request.path

@app.before_request
def load_logged_in_user():
    # Credits: https://flask.palletsprojects.com/en/3.0.x/tutorial/views/
    # Get the user id from the session
    user_id = str(session.get('user_id'))

    # If the user id exists, get the user object from the database
    if user_id is None or not user_id.isdigit():
        g.user = None
    else:
        g.user = get_user_by_user_id(int(user_id))

@app.get('/')
@app.get('/home')
def home():
    top_users = get_top_users(10)
    return render_template('home.jinja', top_users=top_users)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.jinja')
    
    # This is a POST
    # Get the registration info from the form
    first_name = request.form.get('first-name', '')
    last_name = request.form.get('last-name', '')
    hometown = request.form.get('hometown', '')
    gender = request.form.get('gender', '')
    email = request.form.get('email', '')
    birth_date = request.form.get('dob', '')
    password = request.form.get('password', '')

    for field in [first_name, last_name, hometown, gender, email, password]:
        if len(field) == 0:
            flash('Missing required field')
            return render_template('register.jinja')
    
    # Try to add the user to the database
    if not add_user(first_name, last_name, hometown, gender, email, birth_date, password):
        return render_template('register.jinja')
    
    flash('Sucessfully registered. You may log in now.')
    return redirect(url_for('login'))        

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.jinja')

    # This is a POST
    # Get email and password from form
    email = request.form.get('email', '')
    password = request.form.get('password', '')

    for field in [email, password]:
        if len(field) == 0:
            flash('Missing required field')
            return render_template('register.jinja')
    
    # Try to get the user object
    user = get_user_by_login(email, password)
    if user is None:
        flash('Invalid credentials. Please try again.')
        return render_template('login.jinja')
    
    # Credentials were correct
    # Store user ID in session
    session.clear()
    session['user_id'] = user['user_id']
    flash('You have successfuly logged in!')
    return redirect(url_for('home'))

@app.get('/logout')
def logout():
    # Reset session
    session.clear()
    return redirect(url_for('home'))

@app.get('/albums')
def list_albums():
    albums = get_all_albums()
    return render_template('list_albums.jinja', albums=albums, owner=None)

@app.route('/users/<int:owner_id>/albums', methods=['GET', 'POST'])
def user_albums(owner_id: int):
    def render():
        albums = get_albums_by_owner_id(owner_id)
        owner = get_user_by_user_id(owner_id)
        return render_template('list_albums.jinja', albums=albums, owner=owner)

    if request.method == 'GET' or g.user is None or g.user['user_id'] != owner_id:
        # The user is trying to get a list of albums
        return render()

    # The logged in user is in their albums page and trying to create a new album
    album_name = request.form.get('album-name', '')
    if len(album_name) == 0:
        flash('No album name')
        return render()
    
    # Album name was given
    # Create new album
    if not add_album(album_name, owner_id):
        return render()

    flash('Album created. You may add photos now.')
    return render()

@app.route('/albums/show/<int:album_id>', methods=['GET', 'POST'])
def show_album(album_id: int):
    def render():
        photos_dictrows = get_photos_by_album_id(album_id)
        photos = get_photo_info(photos_dictrows, set_album_owner_id=False, set_like_info=True, set_comments=True, set_tags=True)
        is_friend = False if g.user is None else get_friend_status(g.user['user_id'], owner['user_id'])
        return render_template('show_album.jinja', album=album, photos=photos, owner=owner, is_friend=is_friend)

    album = get_album_by_album_id(album_id)
    owner = get_user_by_user_id(album['owner_id'])

    if request.method == 'GET':
        # Show the page
        return render()

    # This is a POST

    if 'add-friend' in request.form:
        add_friend(g.user['user_id'], owner['user_id'])
        return render()

    if 'remove-friend' in request.form:
        remove_friend(g.user['user_id'], owner['user_id'])
        return render()

    if is_post_request_like_or_comment():
        return render()

    flash('Something wrong happened')
    return render()

def is_post_request_like_or_comment():
    if 'like-photo' not in request.form and 'unlike-photo' not in request.form and 'add-comment' not in request.form:
        return False
    
    photo_id = request.form.get('photo-id', '')
    if len(photo_id) == 0 or not photo_id.isdigit():
        flash('Invalid photo id')
        return True
    
    photo_id = int(photo_id)
    
    if 'like-photo' in request.form:
        like_photo(g.user['user_id'], photo_id)
    elif 'unlike-photo' in request.form:
        unlike_photo(g.user['user_id'], photo_id)
    elif 'add-comment' in request.form:
        comment_text = request.form.get('comment', '')
        if len(comment_text) < 3:
            flash('No comment or comment too short')
            return True
        
        user_id = guest_user_id if g.user is None else g.user['user_id']
        add_comment(user_id, photo_id, comment_text)

    return True

@app.route('/albums/edit/<int:album_id>', methods=['GET', 'POST'])
def edit_album(album_id: int):
    def render():
        # Get photos from existing albums
        photo_dictrows = get_photos_by_album_id(album_id)
        photos = get_photo_info(photo_dictrows, set_album_owner_id=False, set_like_info=False, set_comments=False, set_tags=True)
        return render_template('edit_album.jinja', album=album, photos=photos)
    
    album = get_album_by_album_id(album_id)
    
    # Handle errors
    if album is None:
        flash('Album does not exist')
        return redirect(url_for('home'))
    if g.user is None or g.user['user_id'] != album['owner_id']:
        flash('Not allowed')
        return redirect(url_for('home'))
   
    # If GET request, just return results
    if request.method == 'GET':
        return render()
    
    # This is a POST request

    if 'upload-photo' in request.form:
        # Attempting to upload a new photo
        upload_photo(album_id)
        return render()
    
    if 'delete-photo' in request.form:
        # Attemptign to delete a photo
        photo_id = request.form.get('photo-id', '')
        if len(photo_id) == 0 or not photo_id.isdigit():
            flash('Invalid photo id')
            return render()

        photo_id = int(photo_id)    
        if not is_photo_in_album(photo_id, album_id):
            flash('Photo not in album')
            return render()
        
        delete_photo(photo_id)
        return render()
    
    flash('Something went wrong')
    return render()

def upload_photo(album_id: int):
    # Get file and caption
    if 'photo-file' not in request.files:
        flash('Photo file was not attached')
        return
    
    file = request.files.get('photo-file', None)
    caption = request.form.get('caption', '')
    
    # Validate tags string
    tags_string = request.form.get('tags-input', '')
    tag_labels = parse_tags_string(tags_string)
    if tag_labels is None:
        flash('Please enter valid tags and no other symbols')
        return
    
    # Handle errors
    if file.filename == '':
        flash('No selected file')
        return
    if not file or not is_filename_image(file.filename):
        flash('Inappropriate file format')
        return
    
    # Concatenate extension to file
    filename = f'{uuid.uuid4().hex}.{get_extension(file.filename)}'

    # Save the file
    file.save(get_photo_filename_path(filename))

    # Insert photo into database
    photo_id = add_photo(caption, filename, album_id)
    if photo_id is None:
        return
    
    # Create tags
    for tag_label in tag_labels:
        # If tag does not exist
        if not does_tag_exist(tag_label):
            # Create the tag
            if not add_tag(tag_label):
                return
            
    # Add tags to photo
    for tag_label in tag_labels:
        if not add_photo_tag(photo_id, tag_label):
            return
     
    flash('Photo uploaded successfully')

def delete_photo(photo_id: int):
    # Delete the file
    photo_filename = get_photo_filename_by_photo_id(photo_id)
    
    full_filename = get_photo_filename_path(photo_filename)
    try:
        os.remove(full_filename)
    except Exception:
        print(f'Error: Could not remove photo file: {full_filename}')

    # Delete from the database
    cursor = connection.cursor()
    error = None

    try:
        cursor.execute('delete from photos where photo_id = %s', (photo_id,))
    except Exception as e:
        error = f'An error occurred. Please try again later. Error: {e}'

    connection.commit()
    cursor.close()

    if error is not None:
        flash(error)
        return 
    
    flash('Photo deleted successfully')

@app.route('/albums/delete/<int:album_id>', methods=['GET', 'POST'])
def delete_album(album_id: int):
    if g.user is None:
        flash('Not allowed')
        return redirect(url_for('home'))
    
    album = get_album_by_album_id(album_id)

    if album is None:
        flash('Album does not exist')
        return redirect(url_for('home'))
    if g.user['user_id'] != album['owner_id']:
        flash('Not allowed')
        return redirect(url_for('home'))

    # Delete the photo files for this album
    photos = get_photos_by_album_id(album_id)
    
    for photo in photos:
        full_filename = get_photo_filename_path(photo['filename'])
        try:
            os.remove(full_filename)
        except Exception:
            print(f'Error: Could not remove photo file: {full_filename}')

    # Delete the album
    cursor = connection.cursor()
    error = None
    
    try:
        cursor.execute('delete from albums where album_id = %s', (album_id, ))
    except Exception as e:
        error = f'An error occurred. Please try again later. Error: {e}'

    connection.commit()
    cursor.close()

    if error is not None:
        flash(error)
        return redirect(url_for('user_albums', owner_id=g.user['user_id']))

    flash('Album successfully deleted')
    return redirect(url_for('user_albums', owner_id=g.user['user_id']))

@app.route('/photos/search', methods=['GET', 'POST'])
def search_photos():
    def render():
        print(photos)
        return render_template('search_photos.jinja', photos=photos, is_search=is_search, is_my_photos=is_my_photos, famous_tags=famous_tags)
        
    if request.method == 'POST':
        # Try to process the POST request as a like or comment
        if not is_post_request_like_or_comment():
            # Some invalid method was attempted
            flash('Invalid method')

    # Show the page
    famous_tags = get_famous_tags(10)
    tags_string = request.args.get('tags', '')
    user_id = request.args.get('user_id', '')
    user_id = int(user_id) if user_id.isdigit() else None
    is_my_photos = user_id is not None and g.user is not None and g.user['user_id'] == user_id
    photos = []
    is_search = False
    
    if len(tags_string) == 0:
        # No photos to search, show empty page
        return render()
    
    # Search photos by tags
    tag_labels = parse_tags_string(tags_string)
    if tag_labels is None:
        flash('Please enter valid tags and no other symbols')
        return render()

    # Get photos depending on if user id was given
    is_search = True
    photos_dictrows = get_all_photos_by_tags(tag_labels) if user_id is None else get_user_photos_by_tags(tag_labels, user_id)
    photos = get_photo_info(photos_dictrows, set_album_owner_id=True, set_like_info=True, set_comments=True, set_tags=True)
    return render()

@app.route('/photos/recommendations', methods=['GET', 'POST'])
def recommend_photos():
    if g.user is None:
        flash('You must be logged in to get photo recommendations')
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        # Try to process the POST request as a like or comment
        if not is_post_request_like_or_comment():
            # Some invalid method was attempted
            flash('Invalid method')

    # Show the page
    user_id = g.user['user_id']
    user_top_tags = get_user_top_tags(user_id, 5)
    photo_dictrows = get_recommended_photos(user_top_tags, user_id)
    photos = get_photo_info(photo_dictrows, set_album_owner_id=True, set_like_info=True, set_comments=True, set_tags=True)

    return render_template('recommend_photos.jinja', user_top_tags=user_top_tags, photos=photos)

@app.get('/comments/search')
def search_comments():
    """
    Search on Comments functionality
    Submitting form redirects to /comments/search?query=blabla
    If there is query, show results, otherwise just show form
    """
    query = request.args.get('query', '')
    users = [] if len(query) == 0 else get_users_by_comments_containing(query)
    return render_template('search_comments.jinja', users=users, query=query)

@app.route('/users/friends', methods=['GET', 'POST'])
def user_friends():
    if g.user is None:
        flash('You must be logged in to view friends')
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        # Adding or removing a friend
        friend_id = request.form.get('friend-id', '')

        if len(friend_id) == 0:
            flash('Friend id is invalid')
        elif 'add-friend' in request.form:
            add_friend(g.user['user_id'], friend_id)
        elif 'remove-friend' in request.form:
            remove_friend(g.user['user_id'], friend_id)
    
    # Friends
    friends = get_user_friends(g.user['user_id'])

    # Searching
    search_query = request.args.get('query', '')
    search_results = None

    if len(search_query) > 0:
        # Searching for users
        search_results = get_non_friends_by_first_or_last_name_containing(g.user['user_id'], search_query)

    # Recommendations
    recommendations = get_friend_recommendations(g.user['user_id'])

    # Display everything
    return render_template('friends.jinja', friends=friends, search_results=search_results, recommendations=recommendations)

if __name__ == '__main__':
    app.run(debug=True)
