import requests
from bs4 import BeautifulSoup
import random
from PIL import Image
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
            'text': "Describe the image above in a few sentences. Don't describe the style or the colors, but focus on the content of the image. Don't start with an introductory phrase like 'The image depicts / shows...', just describe the image right away."
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
        print(f"Description for {url}: {description}")
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


# Function to generate hints for the current team
def generate_hints(images, current_team, api_key):
    unviewed_images = [img for img in images if not img['viewed']]
    current_team_images = [img for img in unviewed_images if img['card_color'] == current_team]
    other_team_images = [img for img in unviewed_images if
                         img['card_color'] != current_team and img['card_color'] != 'neutral' and img[
                             'card_color'] != 'assassin']
    neutral_images = [img for img in unviewed_images if img['card_color'] == 'neutral']
    assassin_image = [img for img in unviewed_images if img['card_color'] == 'assassin']

    hint_instructions = """
    ### Instructions for Giving Hints in Codenames: Pictures

    **1. Basics of Hints:**
       - **Hint Structure:** A hint consists of one word and a number. The word should relate to one or more pictures on your team's grid, and the number indicates how many pictures it relates to.
       - **Goal:** Help your team identify all of their agents (pictures) before the opposing team finds theirs, without accidentally leading them to guess the assassin.

    **2. Crafting Effective Hints:**
       - **Common Themes:** Look for elements linking multiple pictures on your team's grid (objects, actions, colors, concepts).
       - **Specificity:** Make the hint specific enough to guide your team but broad enough to cover all relevant pictures. Avoid vague hints.
       - **Avoid Ambiguity:** Ensure the hint doesn't relate to pictures on the opposing team’s grid or the assassin. Consider all possible associations.
       - **Cultural Awareness:** Be mindful of your team's cultural context and knowledge to avoid misunderstood references.
       - **Single Word:** Stick to one word, though compound or hyphenated words are allowed if commonly recognized.
       - **Risk Management:** Balance between guiding your team effectively and avoiding dangerous associations, especially with the assassin.

    **3. Using Hints with the Number 0:**
       - **Purpose of 0:** Indicates that none of your team’s pictures are related to the given word. Used strategically to rule out associations and guide your team away from incorrect guesses.
       - **Strategic Application:** 
         - **Example:** If your team has 4 animals (deer, tiger, cat, shark) and the opposing team has 1 animal (boar), you could say "Boar 0." This tells your team to select all animal-related pictures except the boar.
         - **Distraction Elimination:** Steer your team away from incorrect themes.
         - **Assassin Avoidance:** Avoid a picture strongly associated with a dangerous word.

    **4. Examples:**
       - **Positive Hint:** If your pictures include a cat, a lion, and a tiger, you might give the hint "Feline 3."
       - **Negative Hint with 0:** If there are no pictures related to water on your grid but some on the opposing team's grid, you could say "Water 0" to indicate avoiding water-related guesses.

    **5. Considerations for Successful Hints:**
       - **Contextual Relevance:** Think about how your team interprets pictures. Visual elements can be subjective.
       - **Cross-checking:** Mentally check your hint against all pictures on both grids to avoid misleading your team.
       - **Adaptability:** Adapt your strategy based on your team's progress and hints already given. Pay attention to their thought processes.
       - **Numbers:** 2 is kind of average, if you get 3 hints that is good, 4+ is great, but can be risky. Try not to give hints with number 1, unless you have only 1 card left to guess.

    """

    prompt_text = f"""
    Generate a brainstorm on hints for the {current_team} team that describe as many of these images as possible, along with reasoning for each hint.
    Give some different options, and consider all the hint instructions provided below.

    {hint_instructions}

    To conclude, pick a hint that you think is the best and provide a reasoning for it.

    Current team images:
    {chr(10).join([img['description'] for img in current_team_images])}

    Be careful to avoid these images:
    Other team images:
    {chr(10).join([img['description'] for img in other_team_images])}
    Neutral images:
    {chr(10).join([img['description'] for img in neutral_images])}
    Assassin image:
    {chr(10).join([img['description'] for img in assassin_image])}
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
        print("Hint generation result:", result)
        hints = result["choices"][0]["message"]["content"]
        return hints
    else:
        return "Error: Unable to get hints from the API."


# Function to convert hint to JSON
def convert_hint_to_json(hint_with_reasoning, api_key):
    prompt_text = f"""
    Convert the best hint into a JSON object with two fields: 'hint' and 'number'.
    For example: "Feline 3" should be converted to {{"hint": "Feline", "number": 3}}.
    Return just the JSON object starting with {{ and ending with }}.

    {hint_with_reasoning}
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
        print("Hint to JSON conversion result:", result)
        hint_json = result["choices"][0]["message"]["content"]
        return parse_clean_json(hint_json)
    else:
        return {"hint": "", "number": 0}


# Function to generate a list of guesses
def generate_guesses(images, hint, number, api_key, current_team, previous_hints=[]):
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

    Given the images and the hint '{hint} {number}', generate a list of guesses ordered by certainty. When the number is 0, you can guess any number of cards, otherwise, you should guess the number of cards given by the hint. You can guess one card more than the number given by the hint if you are confident.
    Usually it is best to guess the number of cards given by the hint, but you can guess fewer if you are not confident, or more if in the last rounds you didn't guess all the cards.

    Conclude with a list of guesses you would make (so don't include ones you don't want to risk), along with the reasoning for each guess.
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
        print("Guesses generation result:", result)
        guesses = result["choices"][0]["message"]["content"]
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
        print(clean_json_string)
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

    # driver.quit()

    if not enriched_images:
        print("No images found or error in downloading images.")
        return

    print(f"Starting player: {starting_player}")
    for card in enriched_images:
        print(
            f"Card {card['card_number']}: {card['card_color']}, URL: {card['image_url']}, Description: {card['description']}")

    previous_hints = {
        "blue": [],
        "red": []
    }
    current_team = starting_player
    game_over = False
    while not game_over:
        # Generate hints for the current team
        hints_with_reasoning = generate_hints(enriched_images, current_team, api_key)
        print(f"Hints with reasoning for the {current_team} team: {hints_with_reasoning}")

        # Convert hint to JSON
        hint_json = convert_hint_to_json(hints_with_reasoning, api_key)
        hint = hint_json["hint"]
        number = hint_json["number"]
        print(f"Hint JSON for the {current_team} team: {hint_json}")

        # Generate list of guesses
        guesses_with_reasoning = generate_guesses(enriched_images, hint, number, api_key, current_team,
                                                  previous_hints[current_team])
        print(f"Guesses with reasoning: {guesses_with_reasoning}")

        # Convert guesses to JSON
        guesses_json = convert_guesses_to_json(guesses_with_reasoning, api_key)
        print(f"Guesses JSON: {guesses_json}")

        guesses = 0
        correct_guesses = 0
        max_guesses = number + 1 if number != 0 else float('inf')

        for guess in guesses_json:
            if guesses > max_guesses:
                current_team = 'blue' if current_team == 'red' else 'red'
                print(f"Maximum number of guesses reached. Switching to the {current_team} team.")
                break

            print(f"Guess: {guess}")

            card_number = guess['card_number']
            reasoning = guess['reasoning']

            selected_card_index = next(
                (i for i, img in enumerate(enriched_images) if img['card_number'] == card_number), None)
            if selected_card_index is not None:
                selected_card_color = enriched_images[selected_card_index]['card_color']
                enriched_images[selected_card_index]['viewed'] = True

                if selected_card_color == 'assassin':
                    print(f"Game over! {current_team} team selected the assassin.")
                    game_over = True
                    break

                previous_hints[current_team].append(
                    f"I picked card {card_number}, for hint {hint}, because {reasoning}. The card turned out to be {selected_card_color}.")
                print(f"Card {card_number} selected by the {current_team} team. Reasoning: {reasoning}")

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
                            f"I guessed all {number} cards correctly for hint {hint}. This hint does not have to be considered anymore.")
                else:
                    previous_hints[current_team].append(
                        f"I guessed {correct_guesses} cards out of {number} correctly for hint {hint}, and then I guessed card {card_number}, for hint {hint}, because {reasoning}. The card turned out to be {selected_card_color}.")
                    current_team = 'blue' if current_team == 'red' else 'red'
                    print(f"Wrong guess! Switching to the {current_team} team.")
                    break  # Switch turns after a wrong guess

            guesses += 1

    input("Press Enter to continue...")


if __name__ == "__main__":
    main()
