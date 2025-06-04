from flask import Flask, jsonify, request, render_template, redirect, url_for

from supabasePy import SupabaseClient

import threading

supabase = SupabaseClient()

app = Flask(__name__)


@app.route("/")
def home_page():
    return render_template("home.html")


@app.route("/add_user", methods=["GET", "POST"])
def add_user_route():
    if request.method == "POST":
        profile_url = request.form.get("profile_url")
        if profile_url:
            supabase.add_url(profile_url)
            return redirect(url_for("add_user_route"))

    urls = supabase.get_all_urls() or []
    return render_template("add_user.html", urls=urls)


@app.route("/send-facebook-messages", methods=["GET", "POST"])
def send_facebook_messages_route():
    if request.method == "POST":
        message = request.form.get("message")
        selected_group_id = request.form.get("group_id")

        if message:
            # Determine if sending to all or specific group
            if selected_group_id and selected_group_id != "all":
                group_id = int(selected_group_id)
                # Get group info
                groups = supabase.get_all_groups()
                group_name = None
                for group in groups:
                    if group["id"] == group_id:
                        group_name = group["name"]
                        break

                # Store message history
                supabase.store_message_history(message, group_id, group_name)

                # Start background thread for group messaging
                thread = threading.Thread(
                    target=send_facebook_messages, args=(message, group_id)
                )
                thread.start()
                return jsonify(
                    {
                        "status": f"Message sending started for group '{group_name}' in background."
                    }
                )
            else:
                # Send to all users
                supabase.store_message_history(message, None, "All Users")

                # Start background thread for all users
                thread = threading.Thread(
                    target=send_facebook_messages, args=(message, None)
                )
                thread.start()
                return jsonify(
                    {"status": "Message sending started for all users in background."}
                )

    # Get all groups for the dropdown
    groups = supabase.get_all_groups()
    return render_template("send_message.html", groups=groups)


@app.route("/groups", methods=["GET", "POST"])
def groups_route():
    if request.method == "POST":
        action = request.form.get("action")

        if action == "create_group":
            group_name = request.form.get("group_name")
            if group_name:
                supabase.create_group(group_name)
                return redirect(url_for("groups_route"))

        elif action == "manage_group":
            group_id = int(request.form.get("group_id"))
            selected_users = request.form.getlist("selected_users")

            # Get current users in group
            current_users = supabase.get_users_in_group(group_id)
            current_user_ids = []

            for user in current_users:
                if user.get("facebook_profile_urls"):
                    current_user_ids.append(user["facebook_profile_urls"]["id"])
                else:
                    current_user_ids.append(user["profile_id"])

            # Convert selected users to integers
            selected_user_ids = [int(uid) for uid in selected_users]

            # Add new users to group
            for user_id in selected_user_ids:
                if user_id not in current_user_ids:
                    supabase.add_user_to_group(user_id, group_id)

            # Remove users not selected anymore
            for user_id in current_user_ids:
                if user_id not in selected_user_ids:
                    supabase.remove_user_from_group(user_id, group_id)

            return redirect(url_for("groups_route"))

    groups = supabase.get_all_groups()
    all_users = supabase.get_all_profile_urls_with_ids()

    # Get selected group info if requested
    selected_group_id = request.args.get("group_id")
    selected_group = None
    users_in_selected_group = []

    if selected_group_id:
        selected_group_id = int(selected_group_id)
        for group in groups:
            if group["id"] == selected_group_id:
                selected_group = group
                break

        # Get users in selected group
        group_users = supabase.get_users_in_group(selected_group_id)
        for user in group_users:
            if user.get("facebook_profile_urls"):
                users_in_selected_group.append(user["facebook_profile_urls"]["id"])
            else:
                users_in_selected_group.append(user["profile_id"])

    return render_template(
        "groups.html",
        groups=groups,
        all_users=all_users,
        selected_group=selected_group,
        users_in_selected_group=users_in_selected_group,
    )


@app.route("/message-history")
def message_history_route():
    """Route to view message history"""
    history = supabase.get_message_history()
    return render_template("message_history.html", history=history)


def send_facebook_messages(message, group_id=None):
    from playwright.sync_api import sync_playwright
    import time
    import random
    import re

    MESSAGE_INPUT_SELECTOR = 'div[role="textbox"][contenteditable="true"]'

    def send_facebook_message(page, conversation_url, message):
        page.goto(conversation_url)
        time.sleep(5)

        textboxes = page.query_selector_all(MESSAGE_INPUT_SELECTOR)
        if len(textboxes) >= 3:
            try:
                textboxes[2].fill("This is the 3rd textbox filled!")
            except Exception as e:
                print(f"Error filling third textbox: {e}")

        try:
            if textboxes:
                last_textbox = textboxes[-1]
                last_textbox.fill(message)
                time.sleep(1)
                last_textbox.press("Enter")
                print(f"Message sent: {message}")
            else:
                print("No textboxes found.")
        except Exception as e:
            print(f"Could not send message: {e}")

    # Get profile URLs based on group selection
    if group_id:
        profile_urls = supabase.get_urls_for_group(group_id)
        print(
            f"Sending message to group (ID: {group_id}). Found {len(profile_urls)} users."
        )
    else:
        profile_urls = supabase.get_all_urls()
        print(f"Sending message to all users. Found {len(profile_urls)} users.")

    if not profile_urls:
        print("No profile URLs found for the selected group/all users.")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        page.goto("https://www.facebook.com/")
        print("Please log in manually and press Enter to continue...")
        input()

        for profile_url in profile_urls:
            if "id=" in profile_url:
                user_id = profile_url.split("id=")[-1]
                conversation_url = f"https://www.facebook.com/messages/t/{user_id}/"
            else:
                username_match = re.search(r"facebook\.com/(.+)$", profile_url)
                if username_match:
                    username = username_match.group(1)
                    conversation_url = (
                        f"https://www.facebook.com/messages/t/{username}/"
                    )
                else:
                    continue

            send_facebook_message(page, conversation_url, message)
            delay = random.randint(5, 15)
            print(f"Waiting for {delay} seconds before sending the next message...")
            time.sleep(delay)

        browser.close()
        print(f"Finished sending messages to {'group' if group_id else 'all users'}!")


if __name__ == "__main__":
    app.run(debug=True)
