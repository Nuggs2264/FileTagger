### To get a TMDB API key by creating a TMDB account, verifying your email, then visiting your Account Settings → API page on themoviedb.org to request and view your v3 API Key and v4 Read Access Token. Its Free for Personal



#### How to Get a TMDB API Key

Follow these steps based on TMDB’s official documentation and guides:



##### 1\. Create and Verify Your TMDB Account

* Go to themoviedb.org and click Join TMDB to create an account. 
* Open the verification email and confirm your address. Unverified accounts will receive a 401 error when requesting API access. 





##### 2\. Request Your API Key

* After logging in, open Account Settings → API from the left sidebar. This is the only official route to request a key. 
* Accept the API Terms of Use.
* Fill out the short application:

  * Application name
  * Application URL (optional)
  * Summary of how you will use the data
  * Select Developer for personal or non-commercial use. 





##### 3\. Retrieve Your Credentials

Once submitted, the API page will immediately display two credentials:



* API Key (v3) — a 32‑character hex string.
* API Read Access Token (v4) — a long JWT-style token.

Both provide the same level of access according to TMDB’s authentication docs. 



##### 4\. Where to Access Your Key Later

You can always revisit your API keys at:

themoviedb.org/settings/api 



#### The TMDB API is free for non-commercial use with attribution, while commercial use requires a license.

###### Free Usage

The TMDB API allows developers to access movie, TV, and actor data, including images, ratings, trailers, and metadata, for free as long as the project is non-commercial and proper attribution is provided to TMDB. You can request a free API key or a v4 access token from your TMDB account and use it to make API calls. The API supports endpoints like /search/movie, /movie/{id}, /tv/{id}, /person/{id}, trending, and discovery, with responses in JSON format.

##### 

##### Attribution Requirements!!

When using the API, you **must credit TMDB in your application**, typically in an "About" or "Credits" section, and use one of their approved logos. The notice should state: **"This product uses the TMDB API but is not endorsed or certified by TMDB".**

##### 

##### Commercial Use!!

If your project is commercial—meaning it generates revenue or is intended for profit—you must contact TMDB to obtain a commercial license. This involves reaching out to their sales team and following their licensing terms.



##### Rate Limits

For free developer keys, TMDB historically allowed around 40–50 requests per second per IP, which is sufficient for most apps. There are no paid tiers for higher limits, but commercial users may need to review licensing and usage conditions.

##### 

##### Summary

##### Non-commercial projects: Free with attribution

##### Commercial projects: Paid license required

##### API key: Free to obtain

##### 

