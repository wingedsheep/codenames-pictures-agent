# Codenames: Pictures - Automated Spymaster

![](robot.jpg)

This project provides an automated spymaster for the Codenames: Pictures game. It leverages various AI models to generate descriptions of images, create hints, and evaluate guesses. The game is visualized on a grid, where each card represents a picture to be guessed based on hints provided by the spymaster.

## Features

The application offers several features including image description using OpenAI's model, automated grid generation with random assignments for each team's cards, effective hint generation based on image associations, guess evaluation, and game visualization displaying the game grid with card statuses and labels.

## Prerequisites

To run this project, you need Python 3.7 or higher. Additionally, you'll need to install a few Python packages which can be installed via the `requirements.txt` file.

## Installation

Start by cloning the repository:
```bash
git clone https://github.com/your-username/codenames-pictures-automated-spymaster.git
cd codenames-pictures-automated-spymaster
```

It's recommended to set up a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
```

Next, install the required packages:
```bash
pip install -r requirements.txt
```

Create a `settings.json` file in the project root directory and add your API keys:
```json
{
    "openrouter": {
        "apiKey": "your-openrouter-api-key"
    }
}
```

## Usage

You can run the main script with or without visualization. For a more interactive and fun experience, run the visual version of the main script:
```bash
python main_visual.py
```

Alternatively, you can run the non-visual version:
```bash
python main.py
```

The script will open a web browser and navigate to the Codenames: Pictures game. It will automatically download the images, generate descriptions, and display the game grid. The spymaster will provide hints and evaluate guesses until the game concludes.

## Code Overview

The main functionality is orchestrated in `main.py` or `main_visual.py` for a visual experience. The script begins by fetching the API key from a settings file and then describes images using OpenAI's model. It generates the spymaster grid labels and enriches the images with these labels and descriptions.

The game grid is then visualized, showing the status of each card. As the game progresses, the script generates hints for the current team, evaluates the effectiveness of these hints, and updates the game state based on player guesses.

### Generating Hints vs. Guessing

Generating effective hints in Codenames: Pictures is significantly more challenging than guessing. The hint must be a single word that can relate to multiple images on the board, while avoiding associations with images belonging to the opposing team, neutral images, and especially the assassin image. This complexity requires careful consideration and creativity.

To address this challenge, the script generates multiple hints and evaluates each one based on its effectiveness. The evaluation process considers factors such as the strength of association with the target images, the risk of incorrect associations, and the overall clarity of the hint. By scoring and comparing these hints, the script selects the best hint to give to the players, ensuring a higher chance of success.

Here's a closer look at the flow of the script:

1. **Fetching API Key**: The script fetches the API key from a settings file to authenticate with the necessary AI services.
2. **Describing Images**: Using OpenAI's model, the script generates detailed descriptions for each image on the game grid.
3. **Generating Grid Labels**: The script randomly assigns grid labels to each card, indicating whether it belongs to the blue team, red team, is neutral, or the assassin.
4. **Downloading and Enriching Images**: The script downloads the images and enriches them with grid labels and descriptions.
5. **Visualizing the Game Grid**: A visual representation of the game grid is created, displaying the cards and their statuses.
6. **Generating Associations and Hints**: For the current team, the script generates associations and multiple potential hints based on the image descriptions and grid labels.
7. **Evaluating and Selecting Hints**: Each generated hint is scored for effectiveness, and the best hint is selected for the players.
8. **Evaluating Guesses**: The script scores and evaluates player guesses, updating the game state accordingly.
9. **Continuing the Game**: The script iteratively provides hints, evaluates guesses, and updates the visualization until the game concludes.

By following this flow, the script ensures an engaging and automated gameplay experience for Codenames: Pictures.

## Contributing

If you'd like to contribute, please fork the repository, create a new branch, make your changes, and submit a pull request.

## License

This project is licensed under the MIT License. See the `LICENSE` file for more details.

If you encounter any issues or have questions, please open an issue on the repository. Enjoy playing Codenames: Pictures with your automated spymaster!