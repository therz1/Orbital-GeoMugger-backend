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

#convert reviews into csv List<List<>> where the inner list represents each review
def get_reviews_with_parent_data():
    print("Streaming all reviews and linking parent location details...")
    
    reviews_group = db.collection_group("reviews").stream()
    dataset = [["location id", "location name", "rating", "reviews", "tag list"]]
    
    # Optional cache so we don't fetch the same location document from the cloud multiple times
    location_cache = {}
    
    for doc in reviews_group:
        review_data = doc.to_dict()
        
        # 1. Climb up the Firestore tree to get the parent Location Document reference
        # doc.reference -> the review document
        # doc.reference.parent -> the 'reviews' subcollection folder
        # doc.reference.parent.parent -> the parent 'location' document reference
        location_doc_ref = doc.reference.parent.parent
        location_id = location_doc_ref.id # This is your "4QEpRzOiDdFZ..." string
        
        # 2. Fetch the location document details (using cache to stay fast)
        if location_id not in location_cache:
            loc_snapshot = location_doc_ref.get()
            if loc_snapshot.exists:
                location_cache[location_id] = loc_snapshot.to_dict()
            else:
                location_cache[location_id] = {}
                
        parent_location_data = location_cache[location_id]
        
        # 3. Safely extract location name from the parent document fields
        location_name = str(parent_location_data.get("LocationName") or parent_location_data.get("locationName") or "")
        
        # 4. Extract rating, review text, and tags from the subcollection review document
        rating = int(review_data.get("rating") or review_data.get("Rating") or 0)
        review_text = str(review_data.get("review") or review_data.get("Review") or "")
        
        raw_tags = parent_location_data.get("allTags") or parent_location_data.get("tags") or []
        tag_list = list(raw_tags.keys())
        
        
        # Step 6: Assemble into your final ordered list
        row = [location_id, location_name, rating, review_text, tag_list]
        dataset.append(row)
    return dataset

# --- Execute and Print the Output ---
my_data_w_header= get_reviews_with_parent_data()
my_data = my_data_w_header[1:]
        
    

#return unique location name in list (List<String>)
def unique_loc(csv):
    #assuming second column is location name and first row is header
    all_location = list(map(lambda x: x[1], csv))
    res = []
    for location in all_location:
        if location not in res:
            res.append(location)
    return res


#return gloabl average rating (double)
def avg_rating(csv):
    #assuming third column is average
    all_rating = list(map(lambda x: x[2], csv))
    mean = sum(all_rating)/len(all_rating)
    return mean

#return local average rating (dict <String: double> location name: avg_rating)
def local_avg(csv):
    all_location = unique_loc(csv)
    res = {}
    for location in all_location:
        loc_review = list(filter(lambda x : x[1] == location, csv))
        res[location] = avg_rating(loc_review)
    return res


def median(rating):
    if (len(rating) % 2 != 0) :
        index = ((len(rating) + 1)// 2 ) -1
        return rating[index]
    else:
        index_1 = (len(rating) // 2) -1
        index_2 = index_1 + 1
        return (rating[index_1] + rating[index_2])/2
    
def median_ind(rating):
    if(len(rating) % 2 != 0):
        return ((len(rating) + 1)// 2 ) -1
    else:
        return (len(rating) // 2) - 1

def upper_quartile(csv):
    sorted_rating = sorted(list(map(lambda x: x[2], csv)))
    upper = sorted_rating[median_ind(sorted_rating) + 1 :]
    return median(upper)
    

        
        
def calc_bayes_avg(csv):
    item_rating = local_avg(csv)
    all_location = item_rating.keys()
    minimum_threshold = upper_quartile(csv)
    global_avg = avg_rating(csv)
    res = {}
    for location in all_location:
        num_rating = len(list(filter(lambda x: x[1] == location, csv)))
        location_avg = item_rating[location]
        coefficient_1 = (num_rating * location_avg)/(num_rating + minimum_threshold)
        coefficient_2 = (minimum_threshold * global_avg)/(num_rating + minimum_threshold)
        bayes_avg = round(coefficient_1 + coefficient_2,3)
        res[location] = bayes_avg
    return res

def topNspots(n):
    res = calc_bayes_avg(my_data)
    name_to_id = {row[1]: row[0] for row in my_data}
    sorted_name = sorted(res.keys(), key = lambda x : res[x], reverse = True)[:n]
    top_id = [];
    for topN in sorted_name:
        if topN in name_to_id:
            top_id.append(name_to_id[topN])
    return top_id
            
        


@app.get("/hottest-spots")
def get_hottest_spots(n: int = 5):
    try:
        global my_data_w_header, my_data
        my_data_w_header = get_reviews_with_parent_data()
        my_data = my_data_w_header[1:]
        
        ranked_id = topNspots(n)
        return {"hottest_spot_ids": ranked_id}
    except Exception as e:
        raise HTTPException(status_code = 500, detail = str(e))
    
print(calc_bayes_avg(my_data))
        

#return dict{string: List<String>} user_id: List
def get_user_with_preferred_tag():

    user_grp = db.collection('user').stream()
    
    res = {}
    
    for user in user_grp:
        user_data = user.to_dict()
        user_id = user.id
        if user_id not in res:
            res[user_id] = user_data['preferredTags']
    return res

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


def jaccard_sim(user, loc):
    loc_set = set(loc)
    user_set = set(user)
    
    numerator = len(loc_set.intersection(user_set))
    denominator = len(loc_set.union(user_set))
    
    if (denominator == 0):
        return 0.0
    else:
        return numerator/denominator


    
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
    
    
    
    