import os
import httpx
from dotenv import load_dotenv

def make_all_profiles_pro():
    # Load env variables from backend/.env
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
    
    # 1. Fetch current profiles
    resp = httpx.get(f"{supabase_url}/rest/v1/profiles", headers=headers)
    if resp.status_code != 200:
        print(f"[-] Failed to fetch profiles: {resp.status_code} - {resp.text}")
        return
        
    profiles = resp.json()
    print(f"[*] Found {len(profiles)} user profile(s) in the database.")
    
    # 2. Update each profile to 'pro'
    success_count = 0
    for p in profiles:
        profile_id = p.get("id")
        update_resp = httpx.patch(
            f"{supabase_url}/rest/v1/profiles",
            headers=headers,
            params={"id": f"eq.{profile_id}"},
            json={"plan": "pro"}
        )
        if update_resp.status_code in (200, 204):
            success_count += 1
            print(f"[+] Success: Upgraded profile {profile_id} to 'pro' tier!")
        else:
            print(f"[-] Failed to update profile {profile_id}: {update_resp.status_code} - {update_resp.text}")
            
    print(f"[*] Upgraded {success_count}/{len(profiles)} profile(s).")

if __name__ == "__main__":
    make_all_profiles_pro()
