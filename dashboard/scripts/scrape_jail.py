#!/usr/bin/env python3
"""
Hunt County Jail Inmate Scraper
Fetches inmate data including mugshots from apps.huntcounty.net
Filters to show only inmates booked in the last N days
"""

import re
import json
import urllib.request
import urllib.parse
import ssl
from datetime import datetime, timedelta
from html import unescape

DATA_DIR = "/home/colton/.openclaw/workspace/dashboard/data"
LIST_URL = "https://apps.huntcounty.net/jail/results.asp"
BOOKING_URL = "https://apps.huntcounty.net/jail/booking.asp"

# Filter to last N days
DAYS_TO_SHOW = 7

def get_context():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

def fetch_jail_list(limit=50):
    """Fetch the jail list page and extract inmate info"""
    ctx = get_context()
    
    req = urllib.request.Request(LIST_URL, data=f"limit={limit}".encode(), method='POST')
    req.add_header('User-Agent', 'Mozilla/5.0')
    
    with urllib.request.urlopen(req, timeout=15, context=ctx) as response:
        html = response.read().decode('utf-8', errors='ignore')
        cookies = response.getheader('Set-Cookie')
    
    # Extract: name, gender, race, booking_date from list table
    # Pattern: <th>NAME</th><td>GENDER</td><td>RACE</td><td>DATE</td>
    pattern = r'<th[^>]*data-released="([^"]*)"[^>]*data-party="(\d+)"[^>]*data-jailid="(\d+)"[^>]*>([^<]+)</th>\s*<td>([^<]*)</td>\s*<td>([^<]*)</td>\s*<td>([^<]*)</td>'
    matches = re.findall(pattern, html)
    
    inmates = []
    for release, party_id, jailing_id, name, gender, race, booking_date in matches:
        inmates.append({
            'party_id': party_id,
            'jailing_id': jailing_id,
            'release_date': release,
            'name': name.strip(),
            'gender': gender.strip(),
            'race': race.strip(),
            'booking_date': booking_date.strip()
        })
    
    return inmates, cookies

def fetch_booking_details(party_id, jailing_id, release_date, cookies):
    """Fetch booking details page for a specific inmate"""
    ctx = get_context()
    
    post_data = f"partyID={party_id}&jailingID={jailing_id}&releaseDate={release_date}"
    
    req = urllib.request.Request(BOOKING_URL, data=post_data.encode(), method='POST')
    req.add_header('User-Agent', 'Mozilla/5.0')
    if cookies:
        req.add_header('Cookie', cookies.split(';')[0])
    
    try:
        with urllib.request.urlopen(req, timeout=10, context=ctx) as response:
            html = response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"  Error fetching {party_id}: {e}")
        return None
    
    return html

def parse_booking_page(html):
    """Parse the booking page HTML to extract details"""
    
    def get_val(label):
        match = re.search(rf'{label}</label><input[^>]*value="([^"]*)"', html)
        return unescape(match.group(1).strip()) if match else ""
    
    details = {
        'dob': get_val('Date of Birth'),
        'height': get_val('Height'),
        'weight': get_val('Weight'),
        'sex': get_val('Sex'),
        'race': get_val('Race'),
        'location': get_val('Location'),
        'so_number': get_val('S/O Number'),
    }
    
    # Get charges and bonds - these are in a table with multiple rows
    # Pattern: <td>CHARGE</td><td>DATE</td>...<td>BOND</td>
    charge_pattern = r'<tbody><tr><td>([^<]+)</td><td[^>]*>[^<]*</td><td>[^<]*</td><td>[^<]*</td><td>([^<]*)</td><td[^>]*>([^<]*)</td></tr>'
    charge_matches = re.findall(charge_pattern, html)
    
    charges = []
    bonds = []
    for charge, bond_type, bond_amount in charge_matches:
        charges.append(charge.strip())
        if bond_amount.strip():
            bonds.append(f"${bond_amount.strip()}")
    
    details['charge'] = "; ".join(charges) if charges else ""
    details['bond'] = ", ".join(bonds) if bonds else ""
    
    # Get mugshot
    mugshot_match = re.search(r'<img[^>]+src="(data:image/[^;]+;base64,[^"]+)"[^>]*>', html)
    details['mugshot'] = mugshot_match.group(1) if mugshot_match else ""
    
    return details

def scrape_inmates(max_inmates=10, days_back=DAYS_TO_SHOW):
    """Main function to scrape inmate data"""
    print(f"Fetching jail list (filtering to last {days_back} days)...")
    inmate_list, cookies = fetch_jail_list(limit=max_inmates)
    print(f"Found {len(inmate_list)} inmates in list")
    
    # Calculate date filter
    today = datetime.now()
    cutoff_date = today - timedelta(days=days_back)
    
    # Parse dates and filter 
    recent_inmates = []
    for inmate in inmate_list:
        try:
            bd = datetime.strptime(inmate['booking_date'], "%m/%d/%Y")
            # Show inmates from the last N days (including cutoff date)
            if bd >= cutoff_date:
                recent_inmates.append(inmate)
                print(f"  ✓ {inmate['name']} - {inmate['booking_date']}")
        except:
            pass
    
    print(f"\nFiltered to {len(recent_inmates)} inmates from last {days_back} days")
    
    if not recent_inmates:
        print("No recent inmates found. Showing all instead...")
        recent_inmates = inmate_list[:10]
    
    # Fetch details for each
    inmates = []
    for i, inmate in enumerate(recent_inmates):
        print(f"Fetching details for {inmate['name']} ({i+1}/{len(recent_inmates)})...")
        
        html = fetch_booking_details(
            inmate['party_id'], 
            inmate['jailing_id'], 
            inmate['release_date'],
            cookies
        )
        
        if html:
            details = parse_booking_page(html)
            full_inmate = {**inmate, **details}
            inmates.append(full_inmate)
            
            mugshot_status = "📷" if details.get('mugshot') else "❌"
            print(f"  -> {full_inmate.get('charge', 'N/A')} - Bond: {full_inmate.get('bond', 'N/A')} {mugshot_status}")
    
    return inmates

def save_data(inmates, filepath=None):
    """Save inmate data to JSON file"""
    if filepath is None:
        filepath = f"{DATA_DIR}/inmates.json"
    
    data = {
        'updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'count': len(inmates),
        'days_shown': DAYS_TO_SHOW,
        'inmates': inmates
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"\nSaved {len(inmates)} inmates to {filepath}")
    return filepath

def main():
    print("=" * 50)
    print("Hunt County Jail Scraper")
    print(f"Showing last {DAYS_TO_SHOW} days")
    print("=" * 50)
    
    inmates = scrape_inmates(max_inmates=30, days_back=DAYS_TO_SHOW)
    save_data(inmates)
    
    # Summary
    with_mugshots = sum(1 for i in inmates if i.get('mugshot'))
    print(f"\nSummary:")
    print(f"  Total: {len(inmates)}")
    print(f"  With mugshots: {with_mugshots}")
    print(f"  Without: {len(inmates) - with_mugshots}")

if __name__ == "__main__":
    main()
