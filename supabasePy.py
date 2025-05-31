from supabase import create_client, Client
import os
from dotenv import load_dotenv

load_dotenv()


class SupabaseClient:
    _instance: Client = None

    def __init__(self):
        if SupabaseClient._instance is None:
            url = os.getenv("SUPABASE_URL")
            key = os.getenv("SUPABASE_KEY")
            SupabaseClient._instance = create_client(url, key)

        self.client = SupabaseClient._instance

    def add_url(self, url: str):
        data = {"url": url}
        response = self.client.table("facebook_profile_urls").insert(data).execute()
        return response.data

    def get_all_urls(self):
        response = self.client.table("facebook_profile_urls").select("url").execute()
        returnable = []
        for item in response.data:
            if "url" in item:
                returnable.append(item["url"])
        return returnable
