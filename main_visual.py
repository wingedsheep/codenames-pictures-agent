import textwrap
import time

import requests
from bs4 import BeautifulSoup
import random
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Configuration
URL = 'https://samdemaeyer.github.io/codenames-pictures/#/play'
description_model = "google/gemini-pro-1.5"
hints_model = "openai/gpt-4o"
guesses_model = "openai/gpt-4o"
json_conversion_model = "anthropic/claude-3-haiku:beta"


# Function to fetch API key from settings file
def fetch_api_key(filepath="settings.json"):
    with open(filepath) as f:
        settings = json.load(f)
    return settings["openrouter"]["apiKey"]


# Function to describe an image using OpenAI
def describe_image(image_url, api_key):
    prompt = [
        {
            'type': 'image_url',
            'image_url': {
                'url': image_url
            }
        },
        {
            'type': 'text',
            'text': "Write a short paragraph, of at least a few sentences, describing the image. Don't describe the drawing style or the colour, but purely focus on the content of the image. Don't start with an introductory phrase like 'The image depicts / shows...', just describe the image right away. Make sure to include enough detail, and describe all aspects of the image."
        }
    ]

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": description_model,
            "messages": [{"role": "user", "content": prompt}]
        }
    )

    if response.status_code == 200:
        result = response.json()
        description = result["choices"][0]["message"]["content"]
        return description
    else:
        return "Error: Unable to get description from the API."


# Function to generate the spymaster grid labels
def generate_spymaster_grid_labels():
    starting_player = random.choice(['blue', 'red'])
    other_player = 'red' if starting_player == 'blue' else 'blue'

    grid_labels = (
            [starting_player] * 8 +
            [other_player] * 7 +
            ['neutral'] * 4 +
            ['assassin']
    )
    random.shuffle(grid_labels)

    return starting_player, grid_labels


# Function to generate descriptions for all image URLs
def generate_descriptions(image_urls, api_key):
    descriptions = []
    for url in image_urls:
        description = describe_image(url, api_key)
        wrapped_description = textwrap.fill(description, width=80)  # Wrap text to 80 characters per line
        print(f"Description for {url}:\n{wrapped_description}\n")
        descriptions.append(description)
    return descriptions


# Function to download and process images from the website
def download_and_enrich_images(driver, grid_labels, descriptions):
    # Parse page source with BeautifulSoup
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    image_elements = soup.find_all('img', class_='card-img')
    image_urls = ['https://samdemaeyer.github.io' + img['src'] for img in image_elements]

    images = []
    for i, (img_url, description) in enumerate(zip(image_urls, descriptions), start=1):
        img_response = requests.get(img_url)
        img = Image.open(BytesIO(img_response.content))
        img_bytes = BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes = img_bytes.getvalue()

        images.append({
            "image_bytes": img_bytes,
            "image_url": img_url,
            "card_number": i,
            "card_color": grid_labels[i - 1],  # Assign pre-generated color
            "description": description,  # Add description
            "viewed": False  # Initialize as not viewed
        })

    return images


# Function to visualize the game grid
def visualize_game_grid(images):
    grid_size = 5
    image_size = 200
    margin = 10
    colors = {
        'blue': 'blue',
        'red': 'red',
        'neutral': 'yellow',
        'assassin': 'black'
    }

    # Create a blank canvas for the grid
    grid_img = Image.new('RGB', (
        grid_size * (image_size + margin) + margin,
        grid_size * (image_size + margin) + margin
    ), 'white')
    draw = ImageDraw.Draw(grid_img)
    font = ImageFont.load_default()

    for i, img_data in enumerate(images):
        img = Image.open(BytesIO(img_data['image_bytes'])).resize((image_size, image_size))
        row = i // grid_size
        col = i % grid_size

        x = col * (image_size + margin) + margin
        y = row * (image_size + margin) + margin

        grid_img.paste(img, (x, y))

        # Draw the number on the image
        draw.text((x + 10, y + 10), str(img_data['card_number']), fill='black', font=font)

        # Draw the circle for the color
        color = colors[img_data['card_color']]
        draw.ellipse([(x + image_size - 20, y + 10), (x + image_size - 10, y + 20)], fill=color)

        # Draw overlay if viewed
        if img_data['viewed']:
            overlay = Image.new('RGBA', (image_size, image_size), (0, 0, 0, 128))
            grid_img.paste(overlay, (x, y), overlay)

    grid_img.show()


# Function to generate associations to avoid and to aim for
def generate_associations(images, current_team, api_key):
    unviewed_images = [img for img in images if not img['viewed']]
    current_team_images = [img for img in unviewed_images if img['card_color'] == current_team]
    other_team_images = [img for img in unviewed_images if
                         img['card_color'] != current_team and img['card_color'] != 'neutral' and img[
                             'card_color'] != 'assassin']
    neutral_images = [img for img in unviewed_images if img['card_color'] == 'neutral']
    assassin_image = [img for img in unviewed_images if img['card_color'] == 'assassin']

    prompt_text = f"""
    Other team images (avoid these, they give points to the other team):
    {chr(10).join([f'Card {img["card_number"]}: {img["description"]}' for img in other_team_images])}

    Neutral images (avoid these. they are not that bad, but they end your turn and don't give points):
    {chr(10).join([f'Card {img["card_number"]}: {img["description"]}' for img in neutral_images])}

    Assassin image (avoid this at all costs, it ends the game):
    {chr(10).join([f'Card {img["card_number"]}: {img["description"]}' for img in assassin_image])}

    Current team images (these are the images you want your team to guess):
    {chr(10).join([f'Card {img["card_number"]}: {img["description"]}' for img in current_team_images])}

    Create two lists of associations:
    - One list of associations to avoid (from other team, neutral, assassin images), grouped by: catastrophic, bad, and not ideal.
    - One list of associations to aim for (from current team images).

    Create a summary with common themes and associations to avoid.
    Create a summary with common themes and associations to aim for.
    """

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": hints_model,
            "messages": [{"role": "user", "content": prompt_text}]
        }
    )

    if response.status_code == 200:
        result = response.json()
        associations = result["choices"][0]["message"]["content"]
        return associations
    else:
        return "Error: Unable to get associations from the API."


# Function to generate a hint
def generate_hint(images, current_team, api_key, associations, previous_hints):
    unviewed_images = [img for img in images if not img['viewed']]
    current_team_images = [img for img in unviewed_images if img['card_color'] == current_team]
    other_team_images = [img for img in unviewed_images if
                         img['card_color'] != current_team and img['card_color'] != 'neutral' and img[
                             'card_color'] != 'assassin']
    neutral_images = [img for img in unviewed_images if img['card_color'] == 'neutral']
    assassin_image = [img for img in unviewed_images if img['card_color'] == 'assassin']

    hint_instructions = """

    1. **Word Association:** The hint should be a single word that relates to multiple images on the board.
    2. **Number:** The number of cards related to the hint.
    3. **Clarity:** The hint should be clear and concise, avoiding ambiguity.
    4. **Avoiding Bad Associations:** Ensure the hint does not relate to the assassin, other team, or neutral cards.
    5. **Strong Association:** The hint should strongly relate to the cards you want your team to guess.
    6. **Common Themes:** Look for common themes or connections between the cards.
    7. **Risk Management:** Balance the number of cards with the strength of the association.
    8. **Zero Guesses:** If you don't want your team to guess any cards, use a hint with the number '0'.

    """

    prompt_text = f"""
    Based on the following associations, generate a possible hint.
    
    Hint Instructions:
    {hint_instructions}

    Associations evaluation:
    {associations}

    Other hints we considered. Take into account that this hint should be different from the previous ones:
    {chr(10).join(previous_hints)}

    Other team images (avoid these, they give points to the other team):
    {chr(10).join([f'Card {img["card_number"]}: {img["description"]}' for img in other_team_images])}

    Neutral images (avoid these. they are not that bad, but they end your turn and don't give points):
    {chr(10).join([f'Card {img["card_number"]}: {img["description"]}' for img in neutral_images])}

    Assassin image (avoid this at all costs, it ends the game):
    {chr(10).join([f'Card {img["card_number"]}: {img["description"]}' for img in assassin_image])}

    Current team images (these are the images you want your team to guess):
    {chr(10).join([f'Card {img["card_number"]}: {img["description"]}' for img in current_team_images])}

    Return:
    - A hint consisting of one word and a number. Look at the hint instructions for how to craft an effective hint.
    """

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": hints_model,
            "messages": [{"role": "user", "content": prompt_text}]
        }
    )

    if response.status_code == 200:
        result = response.json()
        hint = result["choices"][0]["message"]["content"]
        return hint
    else:
        return "Error: Unable to get hint from the API."


# Function to score a hint
def score_hint(images, current_team, api_key, hint, associations):
    unviewed_images = [img for img in images if not img['viewed']]
    current_team_images = [img for img in unviewed_images if img['card_color'] == current_team]
    other_team_images = [img for img in unviewed_images if
                         img['card_color'] != current_team and img['card_color'] != 'neutral' and img[
                             'card_color'] != 'assassin']
    neutral_images = [img for img in unviewed_images if img['card_color'] == 'neutral']
    assassin_image = [img for img in unviewed_images if img['card_color'] == 'assassin']

    prompt_text = f"""
    Based on the following hint, evaluate its effectiveness.

    Hint: {hint}

    Associations evaluation:
    {associations}

    Other team images (avoid these, they give points to the other team):
    {chr(10).join([f'Card {img["card_number"]}: {img["description"]}' for img in other_team_images])}

    Neutral images (avoid these. they are not that bad, but they end your turn and don't give points):
    {chr(10).join([f'Card {img["card_number"]}: {img["description"]}' for img in neutral_images])}

    Assassin image (avoid this at all costs, it ends the game):
    {chr(10).join([f'Card {img["card_number"]}: {img["description"]}' for img in assassin_image])}

    Current team images (these are the images you want your team to guess):
    {chr(10).join([f'Card {img["card_number"]}: {img["description"]}' for img in current_team_images])}

    Provide:
    - For each unviewed image:
        - assign a score from 1 to 10, indicating how associated the image is with the hint.
    - Give a general score between 1 and 10 (with one decimal), indicating how good the hint is overall.
        - High association with the assassin should result in a very low score.
        - High association with other team images should result in a reduced score.
        - High association with neutral images should result in a slightly reduced score.
        - High association with current team images should result in a higher score.
        - More images should result in a higher score (1 is bad, 2 is average, 3 is good, 4+ is great, but can be risky)
        - A hint that avoids bad associations and focuses on good ones should result in a higher score.
        - Be critical of the hint.

    Return word and number for the hint, general_score and short reasoning for the evaluation.
    """

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": hints_model,
            "messages": [{"role": "user", "content": prompt_text}]
        }
    )

    if response.status_code == 200:
        result = response.json()
        hint_evaluation = result["choices"][0]["message"]["content"]
        return hint_evaluation
    else:
        return "Error: Unable to get hint evaluation from the API."


# Adjusted function to generate the best hint
def generate_best_hint(images, current_team, api_key):
    print(f"Evaluating associations for the {current_team} team...")
    associations = generate_associations(images, current_team, api_key)

    hint1 = generate_hint(images, current_team, api_key, associations, [])
    hint1_evaluation = score_hint(images, current_team, api_key, hint1, associations)
    hint1_json = convert_hint_evaluation_to_json(hint1_evaluation, api_key)
    print(f"First hint considered: {hint1_json['word']} {hint1_json['number']} with general score {hint1_json['general_score']}.")
    hint1_wrapped_reasoning = textwrap.fill(hint1_json['reasoning'], width=80)
    print(f"Reasoning: {hint1_wrapped_reasoning}\n")

    hint1_plus_evaluation = f"Hint: {hint1_json['word']} {hint1_json['number']}. Evaluation: {hint1_json['reasoning']}"
    hint2 = generate_hint(images, current_team, api_key, associations, [hint1_plus_evaluation])
    hint2_evaluation = score_hint(images, current_team, api_key, hint2, associations)
    hint2_json = convert_hint_evaluation_to_json(hint2_evaluation, api_key)
    print(f"Second hint considered: {hint2_json['word']} {hint2_json['number']} with general score {hint2_json['general_score']}. Reasoning: {hint2_json['reasoning']}")
    hint2_wrapped_reasoning = textwrap.fill(hint2_json['reasoning'], width=80)
    print(f"Reasoning: {hint2_wrapped_reasoning}\n")

    hints = [hint1_json, hint2_json]
    best_hint = max(hints, key=lambda x: x['general_score'])

    return best_hint


# Function to convert hint evaluation to JSON
def convert_hint_evaluation_to_json(hint_evaluation, api_key):
    prompt_text = f"""
    Convert the following hint evaluation into a JSON object with fields: 'word', 'number', 'reasoning', and 'general_score'.
    Return just the JSON object starting with {{ and ending with }}.

    {hint_evaluation}
    """

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": json_conversion_model,
            "messages": [{"role": "user", "content": prompt_text}]
        }
    )

    if response.status_code == 200:
        result = response.json()
        hint_json = result["choices"][0]["message"]["content"]
        return parse_clean_json(hint_json)
    else:
        return {"word": "", "number": 0, "reasoning": "", "general_score": 0}


# Function to generate a list of guesses
def generate_guesses(images, word, number, api_key, current_team, previous_hints=[]):
    unviewed_images = [img for img in images if not img['viewed']]

    if not unviewed_images:
        return "No cards available to select."

    guess_instructions = """
    ### Instructions for Guessing in Codenames: Pictures

    **1. Basics of Guessing:**
       - **Guess Structure:** Provide a list of card numbers and reasons for each guess. Order the list based on the certainty of each guess, with the most certain guess first.
       - **Goal:** Identify all of your team's agents based on the given hint, avoiding the assassin and the opposing team's agents.

    **2. Considerations for Successful Guessing:** 
        - **Hint Interpretation:** Match the hint to the image descriptions, considering previous hints and guesses. 
        - **Association:** Ensure the guesses are strongly associated with the hint. Avoid ambiguous associations. 
        - **Previous Hints:** After guessing all cards related to the current hint, you can consider previous hints that were not fully guessed for the extra 1 guess you can make. Don't use this if you are not confident, or if you have already guessed all cards related to the previous hints.
        - **Risk Management:** Balance between confident guesses and avoiding the assassin or opposing team's cards. If you don't know, don't guess more than the number you got with the current hint. 

    """

    prompt_text = f"""
    You are on the {current_team} team.

    Previous information: {chr(10).join(previous_hints)}

    Images descriptions:
    {chr(10).join([f'Card {img["card_number"]}: {img["description"]}' for img in unviewed_images])}

    {guess_instructions}
    
    You received the hint "{word} {number}". Based on this hint, you need to guess the cards related to this hint.
    First create a list of each card with a score between 1 and 10, indicating how certain you are that the card is related to the hint.

    Conclude with a list of guesses you want to make (so don't include ones you don't want to risk), along with the reasoning for each guess.
    Don't make more guesses for the current hint than the number you received with the hint. If you have extra guesses, you can consider previous hints that were not fully guessed, but only if you are confident.
    This list should include the card number and the reasoning for each guess.
    """

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": guesses_model,
            "messages": [{"role": "user", "content": prompt_text}]
        }
    )

    if response.status_code == 200:
        result = response.json()
        guesses = result["choices"][0]["message"]["content"]
        # print(f"Guesses with reasoning: {guesses}")
        return guesses
    else:
        return "Error: Unable to get guesses from the API."


# Function to convert guesses to JSON
def convert_guesses_to_json(guesses, api_key):
    prompt_text = f"""
    Convert the following guesses into a valid JSON list with fields: 'card_number' (integer) and 'reasoning' (string).
    Return just the JSON object, starting with [ and ending with ].

    {guesses}
    """

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": json_conversion_model,
            "messages": [
                {"role": "user", "content": prompt_text}
            ]
        }
    )

    if response.status_code == 200:
        result = response.json()
        guesses_json = result["choices"][0]["message"]["content"]
        return parse_clean_json(guesses_json)
    else:
        return []


def parse_clean_json(message_content):
    # Find the first occurrences of '[' and '{'
    first_square_bracket = message_content.find("[")
    first_curly_bracket = message_content.find("{")

    # Determine which comes first, or if neither is present
    if first_square_bracket == -1 and first_curly_bracket == -1:
        raise Exception("Failed to parse json")

    if first_square_bracket != -1 and (first_curly_bracket == -1 or first_square_bracket < first_curly_bracket):
        start_index = first_square_bracket
        end_index = message_content.rfind("]")
    else:
        start_index = first_curly_bracket
        end_index = message_content.rfind("}")

    # Check if the closing bracket was found
    if end_index == -1:
        raise Exception("Failed to parse json")

    clean_json_string = message_content[start_index:end_index + 1]

    # Replace escaped newlines and convert to JSON
    clean_json_string = clean_json_string.replace('\\n', '')

    try:
        json_data = json.loads(clean_json_string)
    except json.JSONDecodeError:
        raise Exception("Failed to decode json")

    return json_data


# Main function to coordinate the grid generation, image download, description, and hint generation
def main():
    # Fetch API key
    api_key = fetch_api_key()

    # Generate spymaster grid labels
    starting_player, grid_labels = generate_spymaster_grid_labels()

    # Set up Selenium WebDriver (Chrome in this case)
    driver = webdriver.Chrome()
    driver.get(URL)

    # Wait for images to load
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CLASS_NAME, 'card-img'))
        )
    except Exception as e:
        print(f"Error: {e}")
        driver.quit()
        return []

    # Use the same browser instance to get image URLs and generate descriptions
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    image_elements = soup.find_all('img', class_='card-img')
    image_urls = ['https://samdemaeyer.github.io' + img['src'] for img in image_elements]

    # Generate descriptions for all image URLs
    descriptions = generate_descriptions(image_urls, api_key)

    # Download and enrich images with the grid labels and descriptions
    enriched_images = download_and_enrich_images(driver, grid_labels, descriptions)

    driver.quit()

    if not enriched_images:
        print("No images found or error in downloading images.")
        return

    print(f"Starting player: {starting_player}")
    # for card in enriched_images:
    #     print(
    #         f"Card {card['card_number']}: {card['card_color']}, URL: {card['image_url']}, Description: {card['description']}")

    visualize_game_grid(enriched_images)

    previous_hints = {
        "blue": [],
        "red": []
    }
    current_team = starting_player
    game_over = False
    while not game_over:
        # Generate hints for the current team
        best_hint = generate_best_hint(enriched_images, current_team, api_key)

        word = best_hint["word"]
        number = int(best_hint["number"])
        print(f"Hint given by the {current_team} team: {word} {number}")

        # Generate list of guesses
        guesses_with_reasoning = generate_guesses(enriched_images, word, number, api_key, current_team,
                                                  previous_hints[current_team])
        # print(f"Guesses with reasoning: {guesses_with_reasoning}")

        # Convert guesses to JSON
        guesses_json = convert_guesses_to_json(guesses_with_reasoning, api_key)
        # print(f"Guesses: {guesses_json}")

        guesses = 0
        correct_guesses = 0
        max_guesses = number + 1 if number != 0 else float('inf')

        end_turn_reason = "All guesses made."

        for guess in guesses_json:
            if guesses > max_guesses:
                end_turn_reason = "Maximum number of guesses reached."
                break

            card_number = guess['card_number']
            reasoning = guess['reasoning']

            selected_card_index = next(
                (i for i, img in enumerate(enriched_images) if img['card_number'] == card_number), None)
            if selected_card_index is not None:
                selected_card_color = enriched_images[selected_card_index]['card_color']
                enriched_images[selected_card_index]['viewed'] = True

                visualize_game_grid(enriched_images)  # Update the visualization

                print(f"Card {card_number} selected by the {current_team} team. Reasoning: {reasoning}")

                if selected_card_color == 'assassin':
                    print(f"Game over! {current_team} team selected the assassin.")
                    game_over = True
                    break

                previous_hints[current_team].append(
                    f"I picked card {card_number}, for hint {word}, because {reasoning}. The card turned out to be {selected_card_color}.")

                # Check if any team has found all their agents
                blue_agents_found = all(img['viewed'] for img in enriched_images if img['card_color'] == 'blue')
                red_agents_found = all(img['viewed'] for img in enriched_images if img['card_color'] == 'red')

                if blue_agents_found or red_agents_found:
                    winning_team = 'blue' if blue_agents_found else 'red'
                    print(f"{winning_team} team wins! All agents found.")
                    game_over = True
                    break

                if selected_card_color == current_team:
                    print(f"Correct guess! The {current_team} team can continue.")
                    correct_guesses += 1
                    if correct_guesses == number:
                        previous_hints[current_team].append(
                            f"I guessed all {number} cards correctly for hint {word}. This hint does not have to be considered anymore.")
                else:
                    previous_hints[current_team].append(
                        f"I guessed {correct_guesses} cards out of {number} correctly for hint {word}, and then I guessed card {card_number}, for hint {word}, because {reasoning}. The card turned out to be {selected_card_color}.")
                    end_turn_reason = "Wrong guess!"
                    break  # Switch turns after a wrong guess

            guesses += 1

            # Sleep for 2 seconds between guesses
            time.sleep(2)

        current_team = 'blue' if current_team == 'red' else 'red'
        if not game_over:
            print(f"Switching to the {current_team} team. Reason: {end_turn_reason}")

    input("Press Enter to continue...")


if __name__ == "__main__":
    main()
