#import necessary libraries
from fastapi import FastAPI, HTTPException
import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from fastapi.middleware.cors import CORSMiddleware

#instantiating FastAPI , getter for location reccs
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # Open access to local mobile emulators
    allow_credentials=True,
    allow_methods=["*"],      # Allows all standard web operations (GET, POST)
    allow_headers=["*"],
)
# Change this line:
cred = credentials.Certificate(r"C:\Users\huizh\Downloads\test\geomugger_serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()


#return dict{string: List<String>} user_id: List<preferredTag>
def get_user_with_preferred_tag():

    user_grp = db.collection('user').stream()
    
    res = {}
    
    for user in user_grp:
        user_data = user.to_dict()
        user_id = user.id
        if user_id not in res:
            res[user_id] = user_data['preferredTags']
    return res

#return dict{string: List<String>} location_id: List<tagName>
def get_location_with_tags():
    location_grp = db.collection("locations").stream()
    res = {}
    
    for location in location_grp:
        location_data = location.to_dict()
        location_id = location.id
        all_tags_dict = location_data.get("allTags", {})
        #might want to include the tagCount too for weighted calculation of jaccard sim
        tagName = list(all_tags_dict.keys())
        if location_id not in res:
            res[location_id] = tagName
    return res


#return double jaccard similarity between two sets.
def jaccard_sim(user, loc):
    loc_set = set(loc)
    user_set = set(user)
    
    numerator = len(loc_set.intersection(user_set))
    denominator = len(loc_set.union(user_set))
    
    if (denominator == 0):
        return 0.0
    else:
        return numerator/denominator


#return dict{string: List<string>} userId: List<locationId> sorted based on descending jaccard similarity score
def get_recommended_spots():
    
    #load data
    user_data = get_user_with_preferred_tag()
    location_data = get_location_with_tags()
    
    res = {}
    
    #sort location id based on jaccard similarity
    for user_id in user_data.keys():
        res[user_id] = sorted(location_data.keys(),
                              key = lambda x: jaccard_sim(user_data[user_id], location_data[x]), 
                              reverse=True)
    return res

print(get_recommended_spots())
    
    
    
    