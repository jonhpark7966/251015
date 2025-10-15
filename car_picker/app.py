from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import streamlit as st
import yaml

from utils import state as game_state
from utils.image import ensure_thumbnail
from utils.parsing import CarRecord, load_or_build_index
from utils.quiz import QuizChoice, QuizQuestion, generate_question, is_correct


def load_config(config_path: Path) -> dict:
    with config_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def main() -> None:
    base_dir = Path(__file__).parent
    config = load_config(base_dir / "config.yaml")

    st.set_page_config(page_title=config["ui"]["title"], layout="wide")
    st.title(config["ui"]["title"])
    st.caption(config["ui"]["subtitle"])

    data_dir = (base_dir / config["paths"]["data_dir"]).resolve()
    index_path = (base_dir / config["paths"]["index_dir"] / "cars_index.json").resolve()
    lexicon_path = (base_dir / config["paths"]["index_dir"] / "lexicon.json").resolve()
    thumbnail_dir = (base_dir / config["paths"]["assets_dir"] / "thumbnails").resolve()

    if "force_rebuild" not in st.session_state:
        st.session_state["force_rebuild"] = False

    with st.sidebar:
        st.header("Settings")
        if st.button("Rebuild index", use_container_width=True):
            st.session_state["force_rebuild"] = True
            st.experimental_rerun()

        st.write("---")
        score = st.session_state.get("score", 0)
        rounds = st.session_state.get("rounds_played", 0)
        accuracy = f"{(score / rounds * 100):.0f}%" if rounds else "-"
        st.metric("Score", score)
        st.metric("Rounds", rounds)
        st.metric("Accuracy", accuracy)

    game_state.init_game_state()

    force_rebuild = st.session_state.pop("force_rebuild", False)

    with st.spinner("Building image index..."):
        records = load_or_build_index(
            data_dir=data_dir,
            index_path=index_path,
            lexicon_path=lexicon_path,
            force_rebuild=force_rebuild,
        )

    if len(records) < config["quiz"]["num_choices"]:
        st.error(
            f"Not enough parsed entries to start the quiz (only {len(records)} found).",
        )
        return

    rng = game_state.get_rng()

    question = game_state.get_current_question()
    if question is None or game_state.has_answered():
        if st.button("Next car", type="primary"):
            question = generate_new_question(records, rng, config)
        elif question is None:
            question = generate_new_question(records, rng, config)
    else:
        st.button("Next car", type="primary", disabled=True)

    if question is None:
        st.warning("Could not load a question. Try rebuilding the index.")
        return

    display_question(question, thumbnail_dir, config)
    render_history()


def generate_new_question(records: List[CarRecord], rng, config) -> Optional[QuizQuestion]:
    try:
        question = generate_question(
            records,
            num_choices=config["quiz"]["num_choices"],
            rng=rng,
        )
    except ValueError as exc:
        st.error(str(exc))
        return None
    game_state.persist_question(question)
    return question


def display_question(question: QuizQuestion, thumbnail_dir: Path, config: dict) -> None:
    image_path = Path(config["paths"]["data_dir"]) / question.image_record.path
    base_dir = Path(__file__).parent
    absolute_image_path = (base_dir / image_path).resolve()
    thumb_path = ensure_thumbnail(
        absolute_image_path,
        thumbnail_dir,
        max_width=config["images"]["thumbnail_width"],
    )

    st.image(str(thumb_path), use_column_width=False)

    options = question.choices
    labels = {choice.label: choice for choice in options}
    radio_key = f"choice_{question.id}"
    option_labels = ["Choose an option"] + list(labels.keys())
    selected_label = st.radio(
        "Which car is this?",
        options=option_labels,
        key=radio_key,
    )
    selected_choice = labels.get(selected_label)
    if selected_choice:
        game_state.set_selected_choice(selected_choice.id)
    else:
        game_state.set_selected_choice(None)

    check_answer_button(question, selected_choice)

    if game_state.has_answered():
        show_feedback(question, selected_choice)


def check_answer_button(question: QuizQuestion, selected_choice: Optional[QuizChoice]) -> None:
    disabled = game_state.has_answered() or selected_choice is None
    if st.button("Check answer", disabled=disabled):
        choice_id = selected_choice.id if selected_choice else ""
        result = is_correct(question, choice_id)
        game_state.register_answer(
            choice_id=choice_id,
            correct=result,
            question=question,
            choice=selected_choice,
        )
        st.experimental_rerun()


def show_feedback(question: QuizQuestion, selected_choice: Optional[QuizChoice]) -> None:
    correct_choice = next(
        choice for choice in question.choices if choice.id == question.correct_choice_id
    )
    if selected_choice and selected_choice.id == correct_choice.id:
        st.success(f"Correct! {correct_choice.label}")
    else:
        selected_text = selected_choice.label if selected_choice else "No selection"
        st.error(f"Incorrect. You picked: {selected_text} / Answer: {correct_choice.label}")


def render_history() -> None:
    history = st.session_state.get("history", [])
    if not history:
        return
    st.subheader("Recent history")
    table = [
        {
            "Result": "O" if entry.correct else "X",
            "Your choice": entry.selected_label,
            "Correct answer": entry.correct_label,
        }
        for entry in history
    ]
    st.table(table)


if __name__ == "__main__":
    main()
