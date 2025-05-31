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
        if message:
            thread = threading.Thread(target=send_facebook_messages, args=(message,))
            thread.start()
            return jsonify({"status": "Message sending started in background."})
    return render_template("send_message.html")


def send_facebook_messages(message):
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

    profile_urls = supabase.get_all_urls()
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


if __name__ == "__main__":
    app.run(debug=True)
