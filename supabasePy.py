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

    # Group management methods
    def get_all_groups(self):
        response = self.client.table("groups").select("*").execute()
        return response.data

    def get_all_profile_urls_with_ids(self):
        response = (
            self.client.table("facebook_profile_urls").select("id, url").execute()
        )
        return response.data

    def get_users_in_group(self, group_id):
        response = (
            self.client.table("group_mapping")
            .select("profile_id, facebook_profile_urls(id, url)")
            .eq("group_id", group_id)
            .execute()
        )
        return response.data

    def add_user_to_group(self, profile_id, group_id):
        # Check if mapping already exists
        existing = (
            self.client.table("group_mapping")
            .select("id")
            .eq("profile_id", profile_id)
            .eq("group_id", group_id)
            .execute()
        )

        if not existing.data:
            data = {"profile_id": profile_id, "group_id": group_id}
            response = self.client.table("group_mapping").insert(data).execute()
            return response.data
        return None

    def remove_user_from_group(self, profile_id, group_id):
        response = (
            self.client.table("group_mapping")
            .delete()
            .eq("profile_id", profile_id)
            .eq("group_id", group_id)
            .execute()
        )
        return response.data

    def create_group(self, name):
        data = {"name": name}
        response = self.client.table("groups").insert(data).execute()
        return response.data

    # Message history and group-specific messaging methods
    def get_urls_for_group(self, group_id):
        """Get all profile URLs for users in a specific group"""
        response = (
            self.client.table("group_mapping")
            .select("facebook_profile_urls(url)")
            .eq("group_id", group_id)
            .execute()
        )
        urls = []
        for item in response.data:
            if item.get("facebook_profile_urls") and item["facebook_profile_urls"].get(
                "url"
            ):
                urls.append(item["facebook_profile_urls"]["url"])
        return urls

    def store_message_history(self, message, group_id=None, group_name=None):
        """Store message history in the database"""
        data = {
            "message": message,
            "group_id": group_id,
            "group_name": group_name,
            "sent_to_all": group_id is None,
        }
        response = self.client.table("message_history").insert(data).execute()
        return response.data

    def get_message_history(self):
        """Get all message history"""
        response = (
            self.client.table("message_history")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        return response.data

    # Facebook Group URLs management methods
    def add_group_url(self, url: str):
        """Add a Facebook group URL to the database"""
        data = {"url": url}
        response = self.client.table("facebook_group_urls").insert(data).execute()
        return response.data

    def get_all_group_urls(self):
        """Get all Facebook group URLs"""
        response = self.client.table("facebook_group_urls").select("url").execute()
        returnable = []
        for item in response.data:
            if "url" in item:
                returnable.append(item["url"])
        return returnable

    def get_all_group_urls_with_ids(self):
        """Get all Facebook group URLs with their IDs"""
        response = self.client.table("facebook_group_urls").select("id, url").execute()
        return response.data

    def delete_group_url(self, url: str):
        """Delete a Facebook group URL from the database"""
        response = (
            self.client.table("facebook_group_urls").delete().eq("url", url).execute()
        )
        return response.data
