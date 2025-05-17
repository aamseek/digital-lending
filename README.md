### **Steps:**

1. **Clone the repository**:  
   * Ensure that app.py and requirements.txt are in the same directory. 
2. **Set Google API Key**:  
   * **Crucial**: Google Places API functionality requires a valid API key.  
   * Method 1 (Recommended for deployment): Environment Variable  
     Open your terminal and set the GOOGLE\_API\_KEY environment variable:  
     export GOOGLE\_API\_KEY='YOUR\_ACTUAL\_GOOGLE\_PLACES\_API\_KEY'

     (On Windows, use set GOOGLE\_API\_KEY=YOUR\_ACTUAL\_GOOGLE\_PLACES\_API\_KEY)  
   * Method 2 (For quick testing, not recommended for production): Edit app.py  
     Replace "YOUR\_GOOGLE\_API\_KEY\_PLACEHOLDER" in app.py with your actual API key.  
     GOOGLE\_API\_KEY \= "YOUR\_ACTUAL\_GOOGLE\_PLACES\_API\_KEY"

3. **Install Dependencies**:  
   * Open your terminal or command prompt.  
   * Navigate to the directory where you saved app.py and requirements.txt.  
   * Create a virtual environment (recommended):  
     python \-m venv venv  
     source venv/bin/activate  \# On Windows: venv\\Scripts\\activate

   * Install the required packages:  
     pip install \-r requirements.txt

4. **Run the Flask Application**:  
   * In your terminal (with the virtual environment activated if you created one), run:  
     python app.py

   * The server will start, typically on http://localhost:5001.

### **API Endpoints:**

* **GET /**  
  * Description: Shows a welcome message and lists available endpoints.  
  * Example: http://localhost:5001/  
* **GET /hospital/nearby**  
  * Description: Finds hospitals near a given set of coordinates.  
  * Query Parameters:  
    * lat (required): Latitude (e.g., 28.635730)  
    * lon (required): Longitude (e.g., 77.332908)  
    * radius (optional): Search radius in meters (default: 5000).  
    * type (optional): Type of place to search (default: hospital). Other examples: doctor, clinic.  
  * Example: http://localhost:5001/hospital/nearby?lat=28.6357\&lon=77.3329\&radius=10000\&type=hospital  
* **GET /hospital/details**  
  * Description: Gets detailed information about a specific place using its Google Place ID.  
  * Query Parameters:  
    * place\_id (required): The Google Place ID (e.g., from the /hospital/nearby response).  
  * Example: http://localhost:5001/hospital/details?place\_id=ChIJN1t\_tDeuEmsRUsoyG83frY4 (Replace with a valid Place ID)  
* **GET /hospital/find\_by\_name**  
  * Description: Searches for a hospital by its name. It first geocodes the name to find coordinates, then searches for nearby places and attempts to match the name.  
  * Query Parameters:  
    * name (required): The name of the hospital (e.g., Max Super Speciality Hospital, Vaishali).  
    * type (optional): The type of place (default: hospital). E.g., Fertility clinic.  
  * Example: http://localhost:5001/hospital/find\_by\_name?name=Max%20Super%20Speciality%20Hospital,%20Vaishali\&type=hospital  
* **GET /doctors/lybrate**  
  * Description: Scrapes doctor information from lybrate.com for a specified city and specialty.  
  * Query Parameters:  
    * city (required): The city name (e.g., delhi, mumbai).  
    * specialty (required): The doctor's specialty (e.g., dentist, gynaecologist, general-physician). Use URL-friendly names (lowercase, hyphens for spaces).  
    * page (optional): Page number for pagination (default: 1).  
  * Example: http://localhost:5001/doctors/lybrate?city=delhi\&specialty=dentist\&page=1

### **Important Notes for Lybrate Scraping:**

* **Legality and Terms of Service**: Web scraping can be against the terms of service of websites like Lybrate. Always scrape responsibly and ethically. Frequent, aggressive scraping can lead to your IP being blocked.  
* **HTML Structure Changes**: The Lybrate scraper relies on the HTML structure of their website. If Lybrate changes its website design, the scraper might break and would need to be updated. The selectors used are based on the provided notebook and common web patterns but are inherently fragile.  
* **Rate Limiting/Blocks**: Lybrate might have anti-scraping measures. If you make too many requests too quickly, your IP could be temporarily or permanently blocked. The provided code does not include advanced anti-scraping techniques (like proxies or sophisticated user-agent rotation).  
* **Data Accuracy**: The scraped data is only as accurate as what's presented on Lybrate at the time of scraping.

This Flask application provides a unified way to access the functionalities from your notebooks. Remember to handle the Google API key correctly for the hospital-related endpoints to function.