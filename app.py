from flask import Flask, request, jsonify
import pandas as pd
import numpy as np
import requests # For GooglePlaces class and Lybrate
import json # For GooglePlaces class
import time # For GooglePlaces class
import googlemaps # For geocoding hospital names
from bs4 import BeautifulSoup # For Lybrate scraping
import os
import re

app = Flask(__name__)

# --- Configuration ---
# IMPORTANT: Set your Google API Key here or via an environment variable
# For example, in your terminal: export GOOGLE_API_KEY='YOUR_ACTUAL_API_KEY'
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "YOUR_GOOGLE_API_KEY_PLACEHOLDER")
if GOOGLE_API_KEY == "YOUR_GOOGLE_API_KEY_PLACEHOLDER":
    print("WARNING: GOOGLE_API_KEY is not set. Please set it as an environment variable or in the script.")

gmaps_client = googlemaps.Client(key=GOOGLE_API_KEY)

# --- Google Places API Functionality (from notebooks) ---
class GooglePlaces(object):
    def __init__(self, apiKey):
        super(GooglePlaces, self).__init__()
        self.apiKey = apiKey

    def search_places_by_coordinate(self, location, radius, types):
        endpoint_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        places = []
        params = {
            'location': location,
            'radius': radius,
            'types': types,
            'key': self.apiKey
        }
        try:
            res = requests.get(endpoint_url, params=params, timeout=10)
            res.raise_for_status()  # Raise an exception for HTTP errors
            results = res.json()
            places.extend(results.get('results', []))
            
            # Handle pagination
            page_count = 0 # Limit number of pages to avoid excessive calls
            max_pages = 2 # Fetch initial + 2 more pages (total 3 pages of results)

            while "next_page_token" in results and page_count < max_pages:
                params['pagetoken'] = results['next_page_token']
                time.sleep(2) # Google API requires a short delay before fetching the next page
                res = requests.get(endpoint_url, params=params, timeout=10)
                res.raise_for_status()
                results = res.json()
                places.extend(results.get('results', []))
                page_count += 1
                if 'next_page_token' not in results:
                    break
        except requests.exceptions.RequestException as e:
            print(f"Error during Google Places API request: {e}")
            return None # Or raise an error / return an error structure
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from Google Places API: {e}")
            return None
        return places

    def get_place_details(self, place_id, fields):
        endpoint_url = "https://maps.googleapis.com/maps/api/place/details/json"
        params = {
            'place_id': place_id, # Corrected from 'placeid'
            'fields': ",".join(fields),
            'key': self.apiKey
        }
        try:
            res = requests.get(endpoint_url, params=params, timeout=10)
            res.raise_for_status()
            place_details = res.json()
            return place_details.get('result') # Return the 'result' part
        except requests.exceptions.RequestException as e:
            print(f"Error fetching place details: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON for place details: {e}")
            return None

google_places_api = GooglePlaces(GOOGLE_API_KEY)

def get_hospital_coordinates(hospital_name):
    """Geocodes a hospital name to get latitude and longitude using googlemaps client."""
    try:
        geocode_result = gmaps_client.geocode(hospital_name)
        if geocode_result and len(geocode_result) > 0:
            lat = geocode_result[0]['geometry']['location']['lat']
            lon = geocode_result[0]['geometry']['location']['lng']
            return lat, lon
        else:
            return None, None
    except Exception as e:
        print(f"Error during geocoding {hospital_name}: {e}")
        return None, None

@app.route('/hospital/nearby', methods=['GET'])
def get_nearby_hospitals():
    """
    Fetches nearby hospitals based on latitude, longitude, and radius.
    Query Params: lat, lon, radius (in meters), type (e.g., hospital)
    """
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    radius = request.args.get('radius', '5000') # Default 5km
    place_type = request.args.get('type', 'hospital') # Default type 'hospital'

    if not lat or not lon:
        return jsonify({"error": "Missing latitude or longitude parameters"}), 400
    
    location = f"{lat},{lon}"
    
    if GOOGLE_API_KEY == "YOUR_GOOGLE_API_KEY_PLACEHOLDER":
        return jsonify({"error": "Google API Key not configured on the server."}), 500

    places_data = google_places_api.search_places_by_coordinate(location, radius, place_type)

    if places_data is None:
        return jsonify({"error": "Failed to fetch data from Google Places API or no results."}), 500
    
    # Simplified response: list of names and place_ids
    hospitals = []
    for place in places_data:
        hospitals.append({
            "name": place.get("name"),
            "place_id": place.get("place_id"),
            "rating": place.get("rating"),
            "user_ratings_total": place.get("user_ratings_total"),
            "vicinity": place.get("vicinity"),
            "location": place.get("geometry", {}).get("location")
        })
    return jsonify(hospitals)

@app.route('/hospital/details', methods=['GET'])
def get_hospital_details_endpoint():
    """
    Fetches details for a specific hospital using its place_id.
    Query Params: place_id
    """
    place_id = request.args.get('place_id')
    if not place_id:
        return jsonify({"error": "Missing place_id parameter"}), 400

    if GOOGLE_API_KEY == "YOUR_GOOGLE_API_KEY_PLACEHOLDER":
        return jsonify({"error": "Google API Key not configured on the server."}), 500

    fields = ['name', 'website', 'formatted_phone_number', 'rating', 'reviews', 'vicinity', 'geometry']
    details = google_places_api.get_place_details(place_id, fields)

    if details:
        return jsonify(details)
    else:
        return jsonify({"error": "Could not retrieve details for the given place_id"}), 404


@app.route('/hospital/find_by_name', methods=['GET'])
def find_hospital_by_name():
    """
    Finds hospital details by its name.
    It first geocodes the name, then searches nearby, and tries to match the name.
    Query Params: name (hospital name), type (e.g., hospital, default: hospital)
    """
    hospital_name_query = request.args.get('name')
    place_type = request.args.get('type', 'hospital') # Default to 'hospital'

    if not hospital_name_query:
        return jsonify({"error": "Missing 'name' parameter for hospital search"}), 400

    if GOOGLE_API_KEY == "YOUR_GOOGLE_API_KEY_PLACEHOLDER":
        return jsonify({"error": "Google API Key not configured on the server."}), 500

    lat, lon = get_hospital_coordinates(hospital_name_query)

    if not lat or not lon:
        return jsonify({"error": f"Could not geocode hospital name: {hospital_name_query}"}), 404

    # Search in a smaller radius around the geocoded point
    # The original notebook used "200" meter radius for name search.
    nearby_places = google_places_api.search_places_by_coordinate(f"{lat},{lon}", "500", place_type) # Increased radius slightly

    if nearby_places is None:
        return jsonify({"error": "Failed to fetch data from Google Places API after geocoding."}), 500
    
    found_hospital_details = None
    for place in nearby_places:
        # Normalize names for comparison (lower case, remove common terms if needed)
        place_name_normalized = place.get('name', '').lower()
        query_name_normalized = hospital_name_query.lower()
        
        # Simple exact match or containment check
        if query_name_normalized in place_name_normalized or place_name_normalized in query_name_normalized :
            fields = ['name', 'website', 'formatted_phone_number', 'rating', 'reviews', 'vicinity', 'geometry', 'place_id']
            details = google_places_api.get_place_details(place['place_id'], fields)
            if details:
                # Check again if the detailed name is a better match
                detailed_name_normalized = details.get('name','').lower()
                if query_name_normalized in detailed_name_normalized or detailed_name_normalized in query_name_normalized:
                    found_hospital_details = details
                    break # Found a good match
    
    if found_hospital_details:
        return jsonify(found_hospital_details)
    else:
        # Fallback: return list of nearby places if no exact match by name was confirmed
        # This provides some results even if the precise name match failed.
        hospitals = []
        for place in nearby_places:
            hospitals.append({
                "name": place.get("name"),
                "place_id": place.get("place_id"),
                "rating": place.get("rating"),
                "vicinity": place.get("vicinity")
            })
        return jsonify({
            "message": f"Exact match for '{hospital_name_query}' not found. Returning nearby places.",
            "potential_matches": hospitals
        }), 200 # 200 because we are returning potential matches

# --- Lybrate Doctor Scraping Functionality ---
def scrape_lybrate_doctors(city, specialty, page=1):
    """
    Scrapes doctor information from Lybrate for a given city, specialty, and page number.
    """
    doctors_data = []
    # Construct URL: lybrate.com/{city}/{specialty}
    # The specialty string from the notebook often included counts like "Dentistry(665)"
    # We need to clean it up for URL construction if it comes in that format.
    # For this API, we expect a clean specialty string like "dentist", "gynaecologist".
    base_url = f"https://www.lybrate.com/{city.lower().replace(' ', '-')}/{specialty.lower().replace(' ', '-')}"
    page_url = f"{base_url}?page={page}"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        response = requests.get(page_url, headers=headers, timeout=15)
        response.raise_for_status() # Check for HTTP errors
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Lybrate page {page_url}: {e}")
        return {"error": f"Could not fetch Lybrate page: {str(e)}", "doctors": []}

    soup = BeautifulSoup(response.content, 'lxml') # Using lxml as it's generally faster

    # The structure from Doctor_rating_lr.ipynb:
    # soup.find('div', {'class': 'grid__col-lt-20 lybMar-top-btm--half lybPad-left-right--quar'})
    # then grid_cells = required_html.findAll('div', {'class': 'grid'})
    # This structure might change. Let's try a more direct approach to find doctor cards.
    # Common pattern for doctor cards on Lybrate: look for elements with itemprop="itemListElement" or similar
    
    # Attempting to find doctor cards. Lybrate's class names can be dynamic or complex.
    # The notebook used 'grid' class, which is very generic.
    # Let's look for a container that holds multiple doctor profiles.
    # Based on typical Lybrate structure, doctor profiles are often within <div> elements
    # that have specific classes or attributes. The notebook's selector was:
    # 'div.grid__col-lt-20 > div.grid' (implicitly)
    
    # Updated selector strategy: find elements that are likely individual doctor cards.
    # This might need adjustment if Lybrate's HTML structure has changed significantly.
    doctor_cards_container = soup.find('div', class_=re.compile(r'grid__col-lt-20')) # Looser match for main container
    if not doctor_cards_container:
        doctor_cards_container = soup # Fallback to search whole soup if specific container not found

    # Try to find individual doctor entries. The notebook used very generic 'div' with class 'grid'.
    # This is highly prone to breaking. A more specific selector is needed.
    # For example, if each doctor has a specific 'itemtype="http://schema.org/Physician"'
    # Or a class like 'doctor-profile-card' (hypothetical)

    # The notebook's logic for extracting details:
    # heading = grid_cell.find('h2', {'itemprop': 'name'})
    # name_link = heading.find('a')
    # name = name_link.get_text().strip()
    # profile_link = name_link['href']
    # degree_tag = grid_cell.find('div', {'class': 'lybEllipsis ly-doctor__degree grid__col-20'})
    # address_tag = grid_cell.find('span', {'itemprop': 'streetAddress'})
    # right_part = grid_cell.findAll('div', {'class': 'grid__col-xs-10 grid--direction-row'}) for rating, exp, charges

    # Let's try to find elements that are likely to be doctor cards.
    # Often these are <article> tags or <div>s with specific schema.org attributes.
    # The class 'grid' is too generic.
    # Looking for elements that might contain an <h2> with itemprop="name"
    
    potential_cards = doctor_cards_container.find_all('div', class_=lambda x: x and 'ly-doctor' in x) # Heuristic
    if not potential_cards: # Fallback to a more generic search if the above fails
        # This is closer to the notebook's very broad 'grid' search, but we need to be careful.
        # The notebook's `grid_cells = required_html.findAll('div', {'class': 'grid'})`
        # followed by `if grid_cell['class'][0] != 'grid' or len(grid_cell['class']) != 1: continue`
        # implies it was looking for <div class="grid"> specifically.
        potential_cards = doctor_cards_container.find_all('div', class_='grid')


    for card in potential_cards:
        # The notebook's filter: `if grid_cell['class'][0] != 'grid' or len(grid_cell['class']) != 1: continue`
        # This was to ensure it's exactly `class="grid"`. We need to be careful applying this if class list is longer.
        if not (card.get('class') and card.get('class') == ['grid']): # Trying to replicate the notebook's specific filter
            # If this filter is too strict, many valid cards might be skipped.
            # Consider removing or adjusting if no results are found.
            # print(f"Skipping card due to class filter: {card.get('class')}")
            pass # Allow to proceed to try and extract, but be mindful this might pick up wrong divs


        name_tag = card.find('h2', itemprop='name')
        if not name_tag or not name_tag.find('a'):
            continue # Skip if essential name link is missing

        name_link_tag = name_tag.find('a')
        name = name_link_tag.get_text(strip=True)
        profile_link = name_link_tag.get('href', '')
        if not profile_link.startswith('http'):
            profile_link = "https://www.lybrate.com" + profile_link if profile_link.startswith('/') else ""
        
        scraped_city = profile_link.split('/')[3] if len(profile_link.split('/')) > 3 else city # Extract city from URL if possible

        degree_tag = card.find('div', class_=re.compile(r'ly-doctor__degree'))
        degree = degree_tag.get_text(strip=True).replace('\n', ' ').replace(',', ';') if degree_tag else "N/A"

        address_tag = card.find('span', itemprop='streetAddress')
        address = address_tag.get_text(strip=True).replace('\n', ' ').replace(',', ';') if address_tag else "N/A"
        
        rating = "0%"
        experience = "0 years experience"
        charges = "N/A"

        # Extracting rating, experience, charges (from 'grid__col-xs-10 grid--direction-row')
        # This part is tricky as class names can be very specific or change.
        # The notebook used: `right_part = grid_cell.findAll('div', {'class': 'grid__col-xs-10 grid--direction-row'})`
        # This selector is also quite generic.
        
        # Attempting to find the block containing rating/experience/charges
        # These are often in a separate div or spans.
        # Let's look for text patterns.
        
        # Votes/Rating (e.g., "95% (123 votes)")
        rating_tag = card.find('span', class_=re.compile(r'lybRating')) # Common class for ratings
        if rating_tag and rating_tag.find('span', class_=re.compile(r'lybRating__percentage')):
            rating_text = rating_tag.find('span', class_=re.compile(r'lybRating__percentage')).get_text(strip=True)
            votes_text_tag = rating_tag.find('span', class_=re.compile(r'lybRating__count'))
            votes_text = votes_text_tag.get_text(strip=True) if votes_text_tag else ""
            rating = f"{rating_text} {votes_text}".strip()
        else: # Fallback to notebook's method if specific rating class not found
            # This requires iterating through multiple divs as in the notebook
            info_blocks = card.find_all('div', class_=re.compile(r'grid__col-xs-10')) # General info blocks
            for block in info_blocks:
                block_text = block.get_text(strip=True)
                if '%' in block_text and 'vote' in block_text.lower(): # Heuristic for rating
                    rating = block_text.replace('\n', ' ')
                    break 
        
        # Experience
        experience_tag = card.find(string=re.compile(r'\d+ Years Experience', re.IGNORECASE))
        if experience_tag:
            experience = experience_tag.strip()
        else: # Fallback
            info_blocks = card.find_all('div', class_=re.compile(r'grid__col-xs-10'))
            for block in info_blocks:
                block_text = block.get_text(strip=True)
                if 'experience' in block_text.lower():
                    experience = block_text.replace('\n', ' ')
                    break
        
        # Consultation Fee / Charges
        fee_tag = card.find('span', itemprop='priceRange')
        if fee_tag:
            charges = fee_tag.get_text(strip=True)
        else: # Fallback
            info_blocks = card.find_all('div', class_=re.compile(r'grid__col-xs-10'))
            for block in info_blocks:
                block_text = block.get_text(strip=True)
                if '₹' in block_text or 'consultation fee' in block_text.lower():
                    charges = block_text.replace('\n', ' ')
                    break
        
        if name: # Only add if a name was found
            doctors_data.append({
                "name": name,
                "profile_link": profile_link,
                "degree": degree,
                "address": address,
                "rating_votes": rating,
                "experience": experience,
                "charges": charges,
                "scraped_specialty": specialty, # The specialty used for search
                "scraped_city": scraped_city
            })
            
    if not doctors_data and potential_cards:
         print(f"Warning: Found {len(potential_cards)} potential doctor cards but extracted no data. Check selectors for page {page_url}")
    elif not potential_cards:
         print(f"Warning: No potential doctor cards found on page {page_url}. Check main card container selector.")


    return {"doctors": doctors_data, "page_url_scraped": page_url, "doctors_found_on_page": len(doctors_data)}

@app.route('/doctors/lybrate', methods=['GET'])
def get_lybrate_doctors():
    """
    Scrapes doctor information from Lybrate.
    Query Params: city, specialty, page (optional, default 1)
    """
    city = request.args.get('city')
    specialty = request.args.get('specialty')
    try:
        page = int(request.args.get('page', '1'))
    except ValueError:
        return jsonify({"error": "Invalid page number"}), 400

    if not city or not specialty:
        return jsonify({"error": "Missing city or specialty parameters"}), 400

    # Basic input cleaning for URL
    city_clean = re.sub(r'[^a-zA-Z0-9\s-]', '', city).strip().lower()
    specialty_clean = re.sub(r'[^a-zA-Z0-9\s-]', '', specialty).strip().lower()
    
    # Replace spaces with hyphens for URL
    city_url_part = city_clean.replace(' ', '-')
    specialty_url_part = specialty_clean.replace(' ', '-')


    scraped_data = scrape_lybrate_doctors(city_url_part, specialty_url_part, page)
    return jsonify(scraped_data)

# --- Root Endpoint ---
@app.route('/')
def home():
    return jsonify({
        "message": "Welcome to the Hospital and Doctor Information API!",
        "endpoints": {
            "/hospital/nearby": "GET (params: lat, lon, radius, type) - Find nearby hospitals.",
            "/hospital/details": "GET (params: place_id) - Get details of a specific hospital.",
            "/hospital/find_by_name": "GET (params: name, type) - Find hospital by name.",
            "/doctors/lybrate": "GET (params: city, specialty, page) - Scrape doctor info from Lybrate."
        },
        "google_api_key_status": "CONFIGURED" if GOOGLE_API_KEY != "YOUR_GOOGLE_API_KEY_PLACEHOLDER" else "NOT CONFIGURED (Functionality limited)"
    })

if __name__ == '__main__':
    # For development, you can run it with debug=True.
    # For production, use a proper WSGI server like Gunicorn or Waitress.
    # Example: gunicorn app:app
    app.run(debug=True, host='0.0.0.0', port=5001) # Changed port to 5001 to avoid conflict if other apps use 5000
