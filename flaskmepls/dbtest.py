from pymongo import MongoClient

# Connect to MongoDB
client = MongoClient('mongodb://192.168.1.123:27017/')
db = client['nethard']

def get_songs():
    songs = []
    for i in db['music'].find():
        songs.append(i)
    return songs

tk = get_songs()

print(tk)
