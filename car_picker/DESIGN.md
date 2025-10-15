# Car Picker Quiz - Design Overview

## Goals
- Deliver a Streamlit quiz that shows a random car photo and asks the player to identify the make, model, and year.
- Provide 10 answer choices per round with strict scoring (all three attributes must match).
- Scale to thousands of images harvested via the `predicting-car-price-from-scraped-data` project.

## Architecture
```
car_picker/
|-- app.py                  # Streamlit UI entry point
|-- config.yaml             # Paths and gameplay defaults
|-- data/                   # Source images (already provided)
|-- assets/
|   `-- thumbnails/         # Cached resized images
|-- index/
|   |-- cars_index.json     # Cached metadata index
|   `-- lexicon.json        # Manufacturer/model alias map
`-- utils/
    |-- parsing.py          # Filename -> metadata extraction
    |-- quiz.py             # Quiz assembly, distractors, scoring
    |-- image.py            # Thumbnail helpers
    `-- state.py            # Streamlit session orchestration
```

## Key Components
- **Streamlit App (`app.py`)** orchestrates UI flow, loads configuration, and wires quiz rounds.
- **Parsing Module** interprets filenames such as `Acura_ILX_2013_...` into canonical `make`, `model`, `year` metadata and persists the index to `index/cars_index.json`.
- **Quiz Module** generates question payloads, builds nine distractors per round, and evaluates answers.
- **Image Module** creates and caches JPEG thumbnails to keep page loads fast.
- **State Module** centralizes `st.session_state` usage for scoring, history, and RNG seeding.

## Data Parsing Strategy
1. **Tokenization**: Split filenames on underscores; ignore the trailing random hash.
2. **Canonicalization**: Resolve manufacturer names via `lexicon.json` (fall back to a curated alias table).
3. **Year Detection**: First 4-digit token within 1950-2030 becomes the model year.
4. **Model Extraction**: Remaining pre-year tokens form the model name, cleaned for display.
5. **Index Build**: Walk `data/`, parse each file, retain entries with complete metadata, and emit JSON for reuse.
6. **Lexicon Maintenance**: Seed lexicon with common aliases and expand it when new patterns appear.

## Quiz Flow
1. **Game Setup**: Load config, hydrate or rebuild the metadata index, and prime session state.
2. **Round Generation**: Pick a target record and draw nine distractors (similar make first, then close years).
3. **Answer Evaluation**: Award one point only when make, model, and year all match; display contextual feedback.
4. **Progress Tracking**: Maintain score, accuracy, and a rolling history of the last 25 rounds.
5. **Persistence**: Cache thumbnails and indexes to avoid repeated heavy work.

## Configuration Highlights (`config.yaml`)
- `quiz.num_choices`: fixed at 10, per requirement.
- `quiz.strict_scoring`: boolean toggle (defaults to `true`).
- `images.thumbnail_width`: thumbnail max width (default 640).
- `paths.*`: relative folders for data, index, and assets.

## Error Handling & Performance
- Skip malformed filenames and log misses for review.
- When thumbnails cannot be generated, fall back to the original image with a warning.
- Rebuild index on demand; otherwise reuse caches for faster startup.
- Pure helper functions (e.g., parsing, distractor selection) are isolated for future unit tests.

## Potential Enhancements
- Adaptive difficulty that reacts to recent accuracy.
- Timed or streak-based bonus modes.
- Optional brand filters or learning playlists.
- Localized UI strings once the core gameplay is stable.
