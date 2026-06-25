#import necessary libraries
import firebase_admin
from firebase_admin import credentials, firestore



# Change this line:
cred = credentials.Certificate(r"C:\Users\huizh\Downloads\geomugger-backend\geomugger_serviceAccountKey.json")
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

#return dict{string: dict {string: int}} location_id: dict {tag name; tag count}>
def get_location_with_tags():
    location_grp = db.collection("locations").stream()
    res = {}
    
    for location in location_grp:
        location_data = location.to_dict()
        location_id = location.id
        all_tags_dict = location_data.get("allTags", {})
        
        tag_count = {}
        for tagName , tagInfo in all_tags_dict.items():
            tag_count[tagName] = int(tagInfo.get("count", 1))
   
        if location_id not in res:
            res[location_id] = tag_count
    return res


#return double jaccard similarity between two sets.
def weighted_jaccard_sim(user, tag_count):
    loc_set = set(tag_count.keys())
    user_set = set(user)
    
    common_tag_set = loc_set.intersection(user_set)
    numerator = len(loc_set.intersection(user_set))
    denominator = len(loc_set.union(user_set))
    
    if (denominator == 0):
        return 0.0

#updated jaccard similarity calculation to include weighted component
    else:
        multiplier = 0.05
        weight = sum(tag_count.get(tag) for tag in common_tag_set)
        weight_multiplier = (1 + (weight * multiplier))
        return numerator/denominator * weight_multiplier


#return dict{string: List<string>} userId: List<locationId> sorted based on descending jaccard similarity score
def update_recommended_spots_in_firestore():
    
    #load data
    user_data = get_user_with_preferred_tag()
    location_data = get_location_with_tags()
    
    res = {}
    
    #sort location id based on jaccard similarity
    for user_id in user_data.keys():
        res[user_id] = sorted(location_data.keys(),
                              key = lambda x: weighted_jaccard_sim(user_data[user_id], location_data[x]), 
                              reverse=True)[:10]
        #limit size to 10 elements to prevent taking up too much space
        db.collection('user').document(user_id).set(
            {"recommendedSpots": res[user_id],
            "updatedAt": firestore.SERVER_TIMESTAMP}, merge= True)



update_recommended_spots_in_firestore()