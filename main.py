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


@app.route("/manage-group-urls", methods=["GET", "POST"])
def manage_group_urls_route():
    """Route for managing Facebook group URLs"""
    if request.method == "POST":
        action = request.form.get("action")

        if action == "add_urls":
            group_urls = request.form.get("group_urls", "").strip()
            if group_urls:
                # Split by lines and process each URL
                urls = [url.strip() for url in group_urls.split("\n") if url.strip()]
                for url in urls:
                    if (
                        url and "facebook.com/groups/" in url
                    ):  # Validate it's a group URL
                        print(f"Adding group URL: {url}")
                        supabase.add_group_url(url)
                return redirect(url_for("manage_group_urls_route"))

        elif action == "delete_url":
            url_to_delete = request.form.get("url_to_delete")
            if url_to_delete:
                supabase.delete_group_url(url_to_delete)
                return redirect(url_for("manage_group_urls_route"))

    group_urls = supabase.get_all_group_urls() or []
    return render_template("manage_group_urls.html", group_urls=group_urls)


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
        selected_action = request.form.get("selected_action", "single")

        if post_text:
            if selected_action == "all_groups":
                # Post to all saved group URLs
                group_urls = supabase.get_all_group_urls()
                if group_urls:
                    # Start background thread for posting to all groups
                    thread = threading.Thread(
                        target=post_to_multiple_groups,
                        args=(group_urls, post_text, media_file_path),
                    )
                    thread.start()
                    return jsonify(
                        {
                            "status": f"Group posting started for {len(group_urls)} groups in background"
                        }
                    )
                else:
                    return jsonify({"status": "No saved group URLs found"})

            elif selected_action == "single" and group_url:
                # Post to single group URL
                # Start background thread for single group posting
                thread = threading.Thread(
                    target=post_to_single_group,
                    args=(group_url, post_text, media_file_path),
                )
                thread.start()
                return jsonify(
                    {"status": f"Group posting started in background for: {group_url}"}
                )

    # Get all saved group URLs for the dropdown
    group_urls = supabase.get_all_group_urls() or []
    return render_template("post_to_groups.html", group_urls=group_urls)


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


def post_to_facebook_group(page, group_url, post_text, media_file_path=None):
    """Function to post to Facebook groups with text and optional media using existing page"""
    import time
    import os

    try:
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
                return False

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
                return False

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
                        print(f"Found existing file input with selector: {selector}")
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
                            print("File chooser dialog intercepted, setting file...")
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

            # Step 5: Find and click the last but one button in bottom left of modal
            print("Looking for buttons in the bottom left of modal...")

            # Look for all buttons in the modal, especially in the bottom area
            bottom_button_selectors = [
                'div[role="dialog"] div[role="button"]',
                'div[role="dialog"] button',
                'div[role="dialog"] [role="button"]',
            ]

            all_buttons = []
            for selector in bottom_button_selectors:
                buttons = page.query_selector_all(selector)
                all_buttons.extend(buttons)

            # Remove duplicates by converting to set of unique elements
            unique_buttons = []
            for button in all_buttons:
                if button not in unique_buttons:
                    unique_buttons.append(button)

            print(f"Found {len(unique_buttons)} buttons in modal")

            if len(unique_buttons) >= 2:
                # Get the last but one (second-to-last) button
                target_button = unique_buttons[-2]  # -2 means second from the end

                # Try to get some info about the button for logging
                try:
                    button_text = target_button.text_content() or ""
                    button_aria = target_button.get_attribute("aria-label") or ""
                    print(
                        f"Target button text: '{button_text}', aria-label: '{button_aria}'"
                    )
                except:
                    print("Found target button (last but one)")

                print("Clicking the last but one button in bottom left...")
                target_button.click()
                time.sleep(5)
                print("✅ Button clicked successfully!")
                return True

            elif len(unique_buttons) == 1:
                print("Only one button found, clicking it...")
                unique_buttons[0].click()
                time.sleep(5)
                print("✅ Single button clicked successfully!")
                return True

            else:
                print("❌ No buttons found in modal")
                return False

        except Exception as e:
            print(f"Error during group posting process: {e}")
            # Try to take a screenshot for debugging
            try:
                page.screenshot(path="debug_screenshot.png")
                print("Debug screenshot saved as debug_screenshot.png")
            except:
                pass
            return False

    except Exception as e:
        print(f"Error in post_to_facebook_group: {e}")
        return False


def post_to_single_group(group_url, post_text, media_file_path=None):
    """Function to post to a single Facebook group with browser automation"""
    from playwright.sync_api import sync_playwright
    import time
    import re

    print(f"Starting single group posting to: {group_url}")

    try:
        # Extract group ID from URL for storage
        group_id_match = re.search(r"/groups/(\d+)", group_url)
        facebook_native_group_id = (
            group_id_match.group(1) if group_id_match else group_url
        )

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()

            # Navigate to Facebook and login
            page.goto("https://www.facebook.com/")
            print("🔑 Please log in manually and press Enter to continue...")
            input()
            print("✅ Login completed! Starting group posting...")

            # Post to the group
            success = post_to_facebook_group(
                page, group_url, post_text, media_file_path
            )

            if success:
                print("✅ Successfully posted to group!")
                # Store message history for Facebook native group post
                supabase.store_message_history(
                    message=post_text,
                    group_id=None,
                    group_name=None,
                    facebook_native_group_id=facebook_native_group_id,
                )
                print(
                    f"📝 Message history stored for Facebook group: {facebook_native_group_id}"
                )
            else:
                print("❌ Failed to post to group")

            # Keep browser open for 10 seconds to see results
            print("Keeping browser open for 10 seconds...")
            time.sleep(10)
            browser.close()

        return success

    except Exception as e:
        print(f"Error in post_to_single_group: {e}")
        return False


def post_to_multiple_groups(group_urls, post_text, media_file_path=None):
    """Function to post to multiple Facebook groups sequentially with single login"""
    from playwright.sync_api import sync_playwright
    import random
    import time

    print(f"Starting bulk posting to {len(group_urls)} groups...")

    successful_posts = 0
    failed_posts = 0

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()

            # Navigate to Facebook and login ONCE
            page.goto("https://www.facebook.com/")
            print("🔑 Please log in manually and press Enter to continue...")
            input()
            print("✅ Login completed! Starting group posting...")

            # Now post to each group using the same browser session
            for i, group_url in enumerate(group_urls, 1):
                try:
                    print(
                        f"\n--- Posting to group {i}/{len(group_urls)}: {group_url} ---"
                    )

                    # Use the existing page to post to the group
                    success = post_to_facebook_group(
                        page, group_url, post_text, media_file_path
                    )

                    if success:
                        successful_posts += 1
                        print(f"✅ Successfully posted to group {i}")
                    else:
                        failed_posts += 1
                        print(f"❌ Failed to post to group {i}")

                    # Add delay between posts (35-45 seconds as requested)
                    if i < len(group_urls):  # Don't delay after the last post
                        delay = random.randint(35, 45)  # 35-45 seconds between posts
                        print(f"⏳ Waiting {delay} seconds before next group...")
                        time.sleep(delay)

                except Exception as e:
                    print(f"❌ Failed to post to {group_url}: {e}")
                    failed_posts += 1

            # Store message history for posting to all Facebook native groups
            if successful_posts > 0:
                supabase.store_message_history(
                    message=post_text,
                    group_id=None,
                    group_name=None,
                    facebook_native_group_id="ALL_FACEBOOK_GROUPS",
                )
                print(f"📝 Message history stored for posting to all Facebook groups")

            # Keep browser open for a moment to see final results
            print(
                f"\n🎉 Bulk posting completed! Keeping browser open for 10 seconds..."
            )
            time.sleep(10)
            browser.close()

    except Exception as e:
        print(f"Error in bulk posting: {e}")

    print(f"\n--- Final Results ---")
    print(f"✅ Successful posts: {successful_posts}")
    print(f"❌ Failed posts: {failed_posts}")
    print(f"📊 Total groups processed: {len(group_urls)}")
    return successful_posts, failed_posts


if __name__ == "__main__":
    app.run(debug=True)
