from playwright.sync_api import sync_playwright
import time
import random
import re

# Define selectors as constants
MESSAGE_INPUT_SELECTOR = 'div[role="textbox"][contenteditable="true"]'


def send_facebook_message(page, conversation_url, message):
    # Navigate to the conversation URL
    page.goto(conversation_url)
    time.sleep(5)  # Wait for the page to load

    # Locate all textboxes
    textboxes = page.query_selector_all(MESSAGE_INPUT_SELECTOR)

    # Fill the third textbox if it exists
    if len(textboxes) >= 3:
        third_textbox = textboxes[2]
        try:
            third_textbox.fill("This is the 3rd textbox filled!")
            print("Filled the third textbox successfully.")
        except Exception as e:
            print(f"Error filling third textbox: {e}")
    else:
        print("Less than 3 textboxes found on the page.")

    # Type the message in the last textbox and send it by pressing Enter
    try:
        if textboxes:
            last_textbox = textboxes[-1]
            last_textbox.fill(message)
            print("Filled the last textbox with the message.")
            time.sleep(1)  # Allow a moment to fill

            # Simulate pressing Enter
            last_textbox.press("Enter")
            print(f"Message sent: {message}")
        else:
            print("No textboxes found.")
    except Exception as e:
        print(f"Could not send message: {e}")


# Define the list of profile URLs
profile_urls = []

# Define the message
message = "Hello from Playwright!"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    # Step 1: Navigate to Facebook's login page
    page.goto("https://www.facebook.com/")

    # Step 2: Wait for user to log in manually
    print("Please log in manually and press Enter to continue...")
    input()  # Wait for user input

    # Loop through each profile URL, create the message URL, and send the message
    for profile_url in profile_urls:
        # Check if the profile URL contains an ID or a username format
        if "id=" in profile_url:
            user_id = profile_url.split("id=")[-1]
            conversation_url = f"https://www.facebook.com/messages/t/{user_id}/"  # Create the message URL with ID
        else:
            # Extract username from the given profile URL directly
            username = re.search(r"facebook\.com/(.+)$", profile_url).group(1)
            conversation_url = f"https://www.facebook.com/messages/t/{username}/"  # Create the message URL with username

        # Send the message
        send_facebook_message(page, conversation_url, message)

        # Wait for a random delay between 5 and 15 seconds
        delay = random.randint(5, 15)
        print(f"Waiting for {delay} seconds before sending the next message...")
        time.sleep(delay)

    # Close the browser after sending all messages
    time.sleep(2)  # Wait before closing
    browser.close()
