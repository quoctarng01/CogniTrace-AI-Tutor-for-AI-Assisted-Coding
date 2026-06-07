import os
from datetime import date
import httpx
from dotenv import load_dotenv

def make_all_cards_due():
    load_dotenv()
    
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
    
    if not supabase_url or not supabase_key:
        print("[-] Error: SUPABASE_URL or SUPABASE_SERVICE_KEY not found in .env")
        return
        
    headers = {
        "Authorization": f"Bearer {supabase_key}",
        "apikey": supabase_key,
        "Content-Type": "application/json",
    }
    
    print(f"[*] Connecting to Supabase at: {supabase_url}")
    
    # 1. Fetch current cards
    resp = httpx.get(f"{supabase_url}/rest/v1/review_cards", headers=headers)
    if resp.status_code != 200:
        print(f"[-] Failed to fetch review cards: {resp.status_code} - {resp.text}")
        return
        
    cards = resp.json()
    print(f"[*] Found {len(cards)} review card(s) in the database.")
    
    # 2. Update each card's next_review_date to today
    today = date.today().isoformat()
    success_count = 0
    for c in cards:
        card_id = c.get("id")
        update_resp = httpx.patch(
            f"{supabase_url}/rest/v1/review_cards",
            headers=headers,
            params={"id": f"eq.{card_id}"},
            json={"next_review_date": today}
        )
        if update_resp.status_code in (200, 204):
            success_count += 1
            print(f"[+] Success: Marked card {card_id} as due today.")
        else:
            print(f"[-] Failed to update card {card_id}: {update_resp.status_code} - {update_resp.text}")
            
    print(f"[*] Marked {success_count}/{len(cards)} card(s) as due today.")

if __name__ == "__main__":
    make_all_cards_due()
