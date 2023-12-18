import os
from flask import Flask, flash, render_template, request, redirect, url_for, session, jsonify
from pymongo import MongoClient
from hashlib import sha256
from bson import ObjectId
from werkzeug.utils import secure_filename
import mutagen

app = Flask(__name__)

# Connect to MongoDB
client = MongoClient('mongodb://192.168.1.123:27017/')
db = client['nethard']
users = db['user']

# Set a secret key for the session
app.secret_key = 'EFF83@zV(*%YrF3x'  # Replace with a random key

@app.route('/')
def index():
    songs = get_songs()
    if 'username' in session:
        username = session.get('username')
        admin = check_admin()
        return render_template('index.html', songs=songs, username=username, admin=admin)
    else: return render_template('index.html', songs=songs)

@app.route('/logout')
def logout():
    # remove the username from the session if it's there
    session.pop('username', None)
    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_pwd = sha256(password.encode()).hexdigest()

        user = users.find_one({'username': username, 'hashedpwd': hashed_pwd})

        if user:
            session['username'] = user['username']
            return redirect(url_for('index'))
        else:
            flash('Login Failed')

    return render_template('login.html')

def check_login():
    # is the even a *username* in session?
    if not session.get('username'): 
        return False
    else: 
        return True

def check_admin():
    username = session.get('username')
    user = users.find_one({'username': username})
    if not user or not user.get('admin'):
        return False
    else: 
        return True
    
@app.route('/admin')
def admin_page():
    # Check if the user is not logged in
    if not check_login():
        return redirect(url_for('login'))

    # Check if the user is not an admin
    if not check_admin():
        return "You're not an admin"

    # If the user is logged in and is an admin
    return render_template('admin.html')

def search_songs(query):
    # This is pseudo-code; the actual implementation will depend on your database
    results = db['music'].find({"$title": {"$search": query}})
    return list(results)

@app.route('/search')
def search():
    query = request.args.get('query', '')
    if query:
        regex = {'$regex': query, '$options': 'i'}  # Case-insensitive search
        search_results = db['music'].find({"title": regex})
        
        # Convert the cursor to a list before iterating
        songs = list(search_results)
        
        # Convert ObjectId to string for each song
        for song in songs:
            song['_id'] = str(song['_id'])
        
        return render_template('music.html', songs=songs)
    else:
        return redirect(url_for('music'))

@app.route('/music')
def music():
    songs = get_songs()
    if 'username' in session:
        username = session.get('username')
        admin = check_admin()
        return render_template('music.html', songs=songs, username=username, admin=admin)
    else: return render_template('music.html', songs=songs)
    
@app.route('/user_favs')
def user_favs():
    if 'username' in session:
        username = session.get('username')
        admin = check_admin()
        # Retrieve the user's data from the database
        user = db['user'].find_one({'username': session['username']})
        # Safely get the favorites using .get() with a default value of an empty list
        favorite_song_ids = user.get('favorites', [])
        # Convert ObjectId to string for each song
        songs = []
        for i in favorite_song_ids:
            # Fetch the song details from the songs collection
            favorite_songs = db['music'].find({'_id': i})
            for song in favorite_songs:
                song['_id'] = str(song['_id'])
                songs.append(song)
        return render_template('user_favs.html', songs=songs, username=username, admin=admin)
    else:
        return redirect(url_for('login'))

@app.route('/add-to-favorites/<song_id>', methods=['POST'])
def add_to_favorites(song_id):
    if 'username' in session:
        user = db['user'].find_one({'username': session['username']})
        # '$addToSet' avoids adding duplicates
        db['user'].update_one({'_id': user['_id']}, {'$addToSet': {'favorites': ObjectId(song_id)}})
        flash('Song added successfully')
    else:
        return redirect(url_for('login'))
    return redirect(url_for('music'))

@app.route('/remove-from-favorites/<song_id>', methods=['POST'])
def remove_from_favorites(song_id):
    if 'username' in session:
        user = db['user'].find_one({'username': session['username']})
        db['user'].update_one({'_id': user['_id']}, {'$pull': {'favorites': ObjectId(song_id)}})
        flash('Song deleted successfully')
    else:
        return redirect(url_for('login'))
    return redirect(url_for('user_favs'))

@app.route('/update-favorite', methods=['POST'])
def update_favorite():
    if 'username' not in session:
        return jsonify(status='error', message='User not logged in'), 403
    
    data = request.get_json()
    song_id = data.get('songId')
    action = data.get('action')
    user = db['users'].find_one({'username': session['username']})
    
    if action == 'add':
        # Add song to favorites
        db['user'].update_one({'_id': user['_id']}, {'$addToSet': {'favorites': ObjectId(song_id)}})
    elif action == 'remove':
        # Remove song from favorites
        db['user'].update_one({'_id': user['_id']}, {'$pull': {'favorites': ObjectId(song_id)}})
    
    return jsonify(status='success', message='Favorite updated')

# so long space cowboy...
# @app.route('/song/<string:song_id>', methods=['GET', 'POST'])
# def song_detail(song_id):
#     # Convert string ID to ObjectId
#     song_id_obj = ObjectId(song_id)
#     song = db['music'].find_one({'_id': song_id_obj})
#     song['_id'] = str(song['_id'])  # Convert ObjectId to string

#     if song:
#         return render_template('song.html', song=song)
#         #return jsonify(song)
#     else: redirect(url_for('index'))

def get_songs():
    songs_list = []
    for song in db['music'].find():
        song['_id'] = str(song['_id'])  # Convert ObjectId to string
        songs_list.append(song)
    return songs_list

@app.route('/delete-song/<string:song_id>', methods=['POST'])
def delete_song(song_id):
    # Check if the user is not logged in
    if not check_login():
        return redirect(url_for('login'))

    # Check if the user is not an admin
    if not check_admin():
        return "You're not an admin"
        
    # Convert string ID to ObjectId
    song_id_obj = ObjectId(song_id)
    song = db['music'].find_one({'_id': song_id_obj})
    if song:
        db['music'].delete_one({'_id': song_id_obj})
        try:
            if os.path.exists(song['path']):
                os.remove(song['path'])
            if os.path.exists(song['cover']):
                os.remove(song['cover'])
            flash('Song deleted successfully')
        except Exception as e:
            app.logger.error(f"Error deleting files: {e}")
            flash('An error occurred while deleting files')
    else:
        flash('Song not found')
        
    return redirect(url_for('manage_songs'))

ALLOWED_EXTENSIONS = 'mp3'

def get_id3(static_path, full_path):
    audio = mutagen.File(full_path)
    # Extract id
    title = audio.tags["TIT2"].text[0]
    artists = audio.tags["TPE1"].text[0]
    album = audio.tags["TALB"].text[0]
    # Get length, returns in float seconds
    length = audio.info.length
    # Magic code that turns float seconds to minutes
    mins, secs = divmod(length, 60)
    mins = round(mins)
    secs = round(secs)
    timeformat = '{:02d}:{:02d}'.format(mins, secs)
    i = [tag for tag in audio.tags if tag.startswith('APIC')]
    if i: 
        artwork = audio.tags[i[0]].data
    else: 
        artwork = None
        print('No artwork, passing...')
    if artwork:
        cover_path = static_path + secure_filename(title) + '.png'
        with open(cover_path, 'wb') as img:
            img.write(artwork)
    else: cover_path = 'null'
    mydict = {
        "title": title, 
        "artists": artists, 
        "album": album, 
        "length": timeformat, 
        "path": full_path, 
        "cover": cover_path
    }
    return mydict

@app.route('/manage_songs', methods=['GET', 'POST'])
def manage_songs():
    # Check if the user is not logged in
    if not check_login():
        return redirect(url_for('login'))

    # Check if the user is not an admin
    if not check_admin():
        return "You're not an admin"
    
    if request.method == 'POST':
        file = request.files['file']
        # Check if the file is one of the allowed types/extensions
        if file:
            file.seek(0)  # Move cursor back to the start of the file
            filename = secure_filename(file.filename)
            static_path = "static/music/"
            full_path = static_path + filename
            file.save(os.path.join(full_path))
            i = db['music'].insert_one(get_id3(static_path, full_path))
            print(f"File uploaded, ID: {i.inserted_id}")
            flash('File uploaded successfully!')
        else:
            flash('Invalid file type')
        
        return redirect(url_for('manage_songs'))
        
    songs = get_songs()
    return render_template('manage_songs.html', songs=songs)

# def get_playlists():
#     playlists = []
#     for i in db['playlist'].find():
#         playlists.append(i)
#     return playlists
    
# @app.route('/manage_playlists', methods=['GET', 'POST'])
# def manage_playlists():
#     # Check if the user is not logged in
#     if not check_login():
#         return redirect(url_for('login'))

#     # Check if the user is not an admin
#     if not check_admin():
#         return "You're not an admin"
    
#     if request.method == 'POST':
#         print('yay')
#     playlists = get_playlists()
#     return render_template('manage_playlists.html', playlists=playlists)

def get_users():
    userlist = []
    for i in users.find():
        userlist.append(i)
    return userlist

@app.route('/manage_users', methods=['GET', 'POST'])
def manage_users():
    # Check if the user is not logged in
    if not check_login():
        return redirect(url_for('login'))

    # Check if the user is not an admin
    if not check_admin():
        return "You're not an admin"
    
    # add user
    if request.method == 'POST':
        usr = request.form['username']
        pwd = request.form['password']
        email = request.form['email']
        usrType = request.form['usrType']

        hashed = sha256(pwd.encode()).hexdigest()
        
        if usr and pwd and email:
            if usrType == 'Admin':
                newuser = {
                    "username": usr, 
                    "hashedpwd": hashed, 
                    "email": email, 
                    "admin": True,
                    "favorites": []
                }
            else: 
                newuser = {
                    "username": usr, 
                    "hashedpwd": hashed, 
                    "email": email, 
                    "admin": False,
                    "favorites": []
                }
            i = users.insert_one(newuser)
            print(f"User added, ID: {i.inserted_id}")
            flash('User added successfully!')
        else:
            flash('Failed')

        return redirect(url_for('manage_users'))
    
    # pass userlist
    userlist = get_users()
    return render_template('manage_users.html', userlist=userlist)

@app.route('/delete-user/<string:user_id>', methods=['POST'])
def delete_user(user_id):
    # Check if the user is not logged in
    if not check_login():
        return redirect(url_for('login'))

    # Check if the user is not an admin
    if not check_admin():
        return "You're not an admin"
        
    # Convert string ID to ObjectId
    user_id_obj = ObjectId(user_id)
    user = db['user'].find_one({'_id': user_id_obj})
    if user:
        db['user'].delete_one({'_id': user_id_obj})
    else:
        flash('User not found')
        
    # pass userlist
    userlist = get_users()
    return render_template('manage_users.html', userlist=userlist)

@app.route('/register', methods=['GET', 'POST'])
def register():
    # add user
    if request.method == 'POST':
        usr = request.form['username']
        pwd = request.form['password']
        email = request.form['email']

        hashed = sha256(pwd.encode()).hexdigest()
        
        if usr and pwd and email:
            newuser = {
                "username": usr, 
                "hashedpwd": hashed, 
                "email": email, 
                "admin": False,
                "favorites": []
            }
            i = users.insert_one(newuser)
            print(f"User added, ID: {i.inserted_id}")
            flash('Registered successfully, you can now login.')
            return redirect(url_for('login'))
        else:
            flash('Registration Failed')
            return redirect(url_for('register'))

    return render_template('register.html')


if __name__ == '__main__':
    app.run(debug=True)