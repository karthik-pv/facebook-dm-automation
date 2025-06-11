import os
from flask import Flask, jsonify, request, render_template, redirect, url_for

from supabasePy import SupabaseClient

import threading
import re

supabase = SupabaseClient()

os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(
    os.getcwd(), "playwright-browsers"
)

app = Flask(__name__)


@app.route("/")
def home_page():
    return render_template("home.html")


@app.route("/add_user", methods=["GET", "POST"])
def add_user_route():
    if request.method == "POST":
        profile_urls = request.form.get("profile_urls", "").strip()
        if profile_urls:
            # Split by lines and process each URL
            urls = [url.strip() for url in profile_urls.split("\n") if url.strip()]
            for url in urls:
                if url:  # Only add non-empty URLs
                    print(url)
                    supabase.add_url(url)
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


# Legacy route for backward compatibility
@app.route("/manage-groups", methods=["GET", "POST"])
def manage_groups():
    return redirect(url_for("groups_route"))


@app.route("/map-group", methods=["POST"])
def map_group():
    group_id = request.form.get("group_id")
    profile_ids = request.form.getlist("profile_ids")
    if group_id and profile_ids:
        # This would need to be implemented in supabasePy.py if not already there
        # supabase.map_profiles_to_group(int(group_id), list(map(int, profile_ids)))
        pass
    return redirect(url_for("groups_route"))


@app.route("/post-to-groups", methods=["GET", "POST"])
def post_to_groups_route():
    """Route for posting to Facebook groups with text and media"""
    if request.method == "POST":
        group_url = request.form.get("group_url")
        post_text = request.form.get("post_text")
        media_file_path = request.form.get("media_file_path")

        if group_url and post_text:
            # Start background thread for group posting
            thread = threading.Thread(
                target=post_to_facebook_group,
                args=(group_url, post_text, media_file_path),
            )
            thread.start()
            return jsonify(
                {"status": f"Group posting started in background for: {group_url}"}
            )

    return render_template("post_to_groups.html")


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

    # Get profile URLs
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
            # Already a conversation URL
            if "/messages/t/" in profile_url:
                conversation_url = profile_url

            # Facebook group URL with user ID: /groups/{group_id}/user/{user_id}/
            elif "/groups/" in profile_url and "/user/" in profile_url:
                # Extract user ID from group URL
                user_match = re.search(r"/user/(\d+)/?", profile_url)
                if user_match:
                    user_id = user_match.group(1)
                    conversation_url = f"https://www.facebook.com/messages/t/{user_id}/"
                    print(f"Extracted user ID {user_id} from group URL: {profile_url}")
                else:
                    print(f"Could not extract user ID from group URL: {profile_url}")
                    continue

            # profile.php?id=xxx
            elif "id=" in profile_url:
                user_id = profile_url.split("id=")[-1]
                # Handle cases where there might be additional parameters after the ID
                if "&" in user_id:
                    user_id = user_id.split("&")[0]
                conversation_url = f"https://www.facebook.com/messages/t/{user_id}/"

            # username style
            else:
                username_match = re.search(r"facebook\.com/([^/?#]+)", profile_url)
                if username_match:
                    username = username_match.group(1)
                    # Skip if it's a groups or pages URL without user info
                    if username in ["groups", "pages", "events", "marketplace"]:
                        print(f"Skipping non-profile URL: {profile_url}")
                        continue
                    conversation_url = (
                        f"https://www.facebook.com/messages/t/{username}/"
                    )
                else:
                    print(f"Invalid URL format: {profile_url}")
                    continue

            send_facebook_message(page, conversation_url, message)
            delay = random.randint(5, 15)
            print(f"Waiting for {delay} seconds before sending the next message...")
            time.sleep(delay)

        browser.close()
        print(f"Finished sending messages to {'group' if group_id else 'all users'}!")


def post_to_facebook_group(group_url, post_text, media_file_path=None):
    """Function to post to Facebook groups with text and optional media"""
    from playwright.sync_api import sync_playwright
    import time
    import os

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()

            # Navigate to Facebook
            page.goto("https://www.facebook.com/")
            print("Please log in manually and press Enter to continue...")
            input()

            # Navigate to the group
            print(f"Navigating to group: {group_url}")
            page.goto(group_url)
            time.sleep(5)

            print(
                "Looking for 'Write something' or 'Create post' button to open post modal..."
            )

            # Step 1: Find and click the button that opens the post creation modal
            try:
                # Try different selectors for the "Write something" button that opens the modal
                modal_trigger_selectors = [
                    '[data-testid="status-attachment-mentions-input"]',
                    '[placeholder*="Write something"]',
                    '[aria-label*="Write something"]',
                    'div[role="button"]:has-text("Write something")',
                    'div:has-text("Write something")',
                    '[data-testid="post-form-textarea"]',
                    'div[role="textbox"][contenteditable="true"]',
                ]

                modal_trigger = None
                for selector in modal_trigger_selectors:
                    modal_trigger = page.query_selector(selector)
                    if modal_trigger:
                        print(f"Found modal trigger with selector: {selector}")
                        break

                if not modal_trigger:
                    print("Could not find 'Write something' button to open post modal")
                    return

                # Click to open the post creation modal
                print("Clicking to open post creation modal...")
                modal_trigger.click()
                time.sleep(3)

                # Step 2: Wait for the post creation modal/popup to appear and find the text input
                print("Waiting for post creation modal to appear...")

                # Try to find the text input area in the modal
                text_input_selectors = [
                    'div[role="dialog"] div[role="textbox"][contenteditable="true"]',
                    'div[aria-label*="Create post"] div[contenteditable="true"]',
                    'div[data-testid="post-composer-form"] div[contenteditable="true"]',
                    'div[contenteditable="true"]:not([role="button"])',
                    '[data-testid="post-composer-text-input"] div[contenteditable="true"]',
                    'div[role="textbox"][contenteditable="true"]',
                ]

                text_input = None
                # Give more time for modal to fully load
                for attempt in range(3):
                    for selector in text_input_selectors:
                        text_input = page.query_selector(selector)
                        if text_input:
                            print(f"Found text input with selector: {selector}")
                            break
                    if text_input:
                        break
                    print(f"Attempt {attempt + 1}: Modal still loading, waiting...")
                    time.sleep(2)

                if not text_input:
                    print("Could not find text input in post modal")
                    return

                # Step 3: Fill in the post text
                print(f"Filling in post text: {post_text}")
                text_input.click()
                time.sleep(1)
                text_input.fill(post_text)
                time.sleep(2)

                # Step 4: Upload media if provided
                if media_file_path and os.path.exists(media_file_path):
                    print(f"Adding media: {media_file_path}")

                    # First, try to find any existing file input elements
                    file_input_selectors = [
                        'div[role="dialog"] input[type="file"]',
                        'input[type="file"][accept*="image"]',
                        'input[type="file"][accept*="video"]',
                        'input[type="file"]',
                    ]

                    file_input = None
                    for selector in file_input_selectors:
                        file_input = page.query_selector(selector)
                        if file_input:
                            print(
                                f"Found existing file input with selector: {selector}"
                            )
                            break

                    if file_input:
                        # Directly set the file without clicking anything
                        print("Setting file directly on existing input...")
                        file_input.set_input_files(media_file_path)
                        time.sleep(3)
                        print("Media file set successfully")
                    else:
                        # If no direct file input found, look for photo/video buttons
                        print("Looking for photo/video buttons to reveal file input...")
                        upload_button_selectors = [
                            'div[role="dialog"] div[aria-label*="Photo/video"]',
                            'div[role="dialog"] div[aria-label*="Add photos/videos"]',
                            'div[role="dialog"] div:has-text("Photo/video")',
                            'div[role="dialog"] svg[aria-label*="Photo/video"]',
                            '[data-testid="photo-upload-button"]',
                            '[aria-label*="Photo/video"]',
                        ]

                        upload_button = None
                        for selector in upload_button_selectors:
                            upload_button = page.query_selector(selector)
                            if upload_button:
                                print(f"Found upload button with selector: {selector}")
                                break

                        if upload_button:
                            # Before clicking, try to find the file input that will be used
                            print("Looking for file input that will be triggered...")

                            # Use page.on to listen for file chooser events
                            def handle_file_chooser(file_chooser):
                                print(
                                    "File chooser dialog intercepted, setting file..."
                                )
                                file_chooser.set_files(media_file_path)

                            # Set up the file chooser event listener
                            page.on("filechooser", handle_file_chooser)

                            # Now click the upload button
                            print("Clicking upload button...")
                            upload_button.click()

                            # Wait for file to be processed
                            time.sleep(4)
                            print("Media uploaded successfully via file chooser")

                            # Remove the event listener
                            page.remove_listener("filechooser", handle_file_chooser)
                        else:
                            print("Could not find upload button in modal")

                # Step 5: Find and click the Post button
                print("Looking for Post button...")
                post_button_selectors = [
                    'div[role="dialog"] div[role="button"]:has-text("Post")',
                    'div[role="dialog"] button:has-text("Post")',
                    '[data-testid="react-composer-post-button"]',
                    'div[aria-label="Post"]',
                    'button[aria-label="Post"]',
                ]

                post_button = None
                for selector in post_button_selectors:
                    post_button = page.query_selector(selector)
                    if post_button:
                        print(f"Found post button with selector: {selector}")
                        break

                if post_button:
                    print("Clicking Post button...")
                    post_button.click()
                    time.sleep(3)  # Wait to see if additional options appear

                    # Check if additional options/tagging screen appeared
                    print("Checking if additional options screen appeared...")

                    # Look for the back arrow button at top left of modal
                    back_button_selectors = [
                        'div[role="dialog"] div[role="button"][aria-label*="Back"]',
                        'div[role="dialog"] button[aria-label*="Back"]',
                        'div[role="dialog"] svg[aria-label*="Back"]',
                        'div[role="dialog"] div[role="button"]:has(svg)',
                        'div[role="dialog"] button:has(svg)',
                        'div[role="dialog"] [aria-label*="Go back"]',
                        'div[role="dialog"] [data-testid*="back"]',
                    ]

                    back_button = None
                    for selector in back_button_selectors:
                        back_button = page.query_selector(selector)
                        if back_button:
                            print(f"Found back button with selector: {selector}")
                            break

                    if back_button:
                        print(
                            "Additional options screen detected, clicking back arrow..."
                        )
                        back_button.click()
                        time.sleep(2)  # Wait for main post screen to return

                        # Now look for the blue Post button again
                        print("Looking for blue Post button after going back...")
                        blue_post_selectors = [
                            'div[role="dialog"] div[role="button"]:has-text("Post")',
                            'div[role="dialog"] button:has-text("Post")',
                            '[data-testid="react-composer-post-button"]',
                            'div[aria-label="Post"]',
                            'button[aria-label="Post"]',
                        ]

                        blue_post_button = None
                        for attempt in range(2):  # Try twice
                            for selector in blue_post_selectors:
                                blue_post_button = page.query_selector(selector)
                                if blue_post_button:
                                    print(
                                        f"Found blue post button with selector: {selector}"
                                    )
                                    break
                            if blue_post_button:
                                break
                            print(
                                f"Attempt {attempt + 1}: Looking for blue post button..."
                            )
                            time.sleep(1)

                        if blue_post_button:
                            print("Clicking blue Post button to submit...")
                            blue_post_button.click()
                            time.sleep(5)
                            print("✅ Post submitted successfully!")
                        else:
                            print("❌ Could not find blue Post button after going back")
                    else:
                        # No back button found, might have posted directly
                        print(
                            "No additional options detected, post may have been submitted directly"
                        )
                        time.sleep(2)
                        print("✅ Post submitted successfully!")
                else:
                    print("❌ Could not find Post button in modal")

            except Exception as e:
                print(f"Error during group posting process: {e}")
                # Try to take a screenshot for debugging
                try:
                    page.screenshot(path="debug_screenshot.png")
                    print("Debug screenshot saved as debug_screenshot.png")
                except:
                    pass

            browser.close()

    except Exception as e:
        print(f"Error in post_to_facebook_group: {e}")


if __name__ == "__main__":
    app.run(debug=True)
