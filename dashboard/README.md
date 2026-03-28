# Greenville, TX Dashboard Project

## Location
- **City:** Greenville, TX 75402
- **County:** Hunt County
- **Timezone:** America/Chicago

## Data Sources

### ✅ Weather (Working)
- **Source:** wttr.in
- **Endpoint:** `https://wttr.in/75402?format=j1`
- **Update:** Real-time

### ❓ Jail Listings
- **Hunt County Sheriff:** huntcountytx.gov (site appears down/blocked)
- **Alternative:** Texas Department of Criminal Justice (tdcj.texas.gov)
- **Need:** Find working inmate lookup URL

### ❓ Traffic
- **Options:**
  - Google Maps API (needs key)
  - Mapbox (free tier)
  - Traffic layer via Leaflet/OpenStreetMap
  - Texas DOT API

### ❓ Facebook Posts
- **Option:** Scrape city Facebook page (if available)

### ❓ Local News
- **Options:**
  - Greenville Herald-Banner (local news)
  - RSS feeds

## Tech Stack
- **Frontend:** HTML + CSS + Vanilla JS
- **Data:** Python scripts for fetching
- **Hosting:** Local (for now)

## Priority
1. ✅ Weather (working)
2. Traffic/Map
3. Jail listings
4. News/Headlines
5. Facebook (optional)

---

## Progress

- [x] Weather API working (75°F Sunny)
- [x] Build HTML dashboard skeleton
- [x] Add OpenStreetMap for traffic view
- [x] Data fetch script working
- [x] Find jail listings source ✅ (apps.huntcounty.net works!)
- [x] Add local news ✅ (Herald Banner)
- [x] Set up daily refresh cron (12am, 12pm)

## Social Media (Future)

- Facebook: Leave out for now
- X (Twitter): Maybe add later
- Focus on reading first, posting later
