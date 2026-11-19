"""Python Test & Study Analyzer 2.0

A CSV-based multiple-choice test application with validation, filters,
randomized tests, optional negative marking, topic analysis, and saved reports.
Uses only the Python standard library.
"""

from __future__ import annotations

import csv
import random
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

OPTIONS = ("A", "B", "C", "D")
HISTORY_FIELDS = (
    "timestamp",
    "quiz_file",
    "subject_filter",
    "difficulty_filter",
    "total_questions",
    "correct",
    "wrong",
    "skipped",
    "net_score",
    "score_percent",
    "accuracy_percent",
    "duration_seconds",
    "report_file",
)


@dataclass
class Question:
    """One validated MCQ from the input CSV file."""

    question: str
    options: Dict[str, str]
    answer: str
    subject: str = "Unspecified"
    topic: str = "Unspecified"
    difficulty: str = "Unspecified"
    explanation: str = ""
    source_row: int = 0


def normalize_header(value: object) -> str:
    """Normalize headers so spaces, hyphens and capitalization do not matter."""
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def get_field(row: dict, *names: str) -> str:
    """Return the first matching CSV field, using flexible header matching."""
    wanted = {normalize_header(name) for name in names}
    for key, value in row.items():
        if key is not None and normalize_header(key) in wanted:
            return str(value or "").strip()
    return ""


def answer_to_letter(answer: str, options: Dict[str, str]) -> Optional[str]:
    """Convert an answer letter or exact option text into A/B/C/D."""
    cleaned = answer.strip()
    upper = cleaned.upper()
    if upper in OPTIONS:
        return upper

    matches = [
        letter
        for letter, option_text in options.items()
        if cleaned.casefold() == option_text.strip().casefold()
    ]
    return matches[0] if len(matches) == 1 else None


def load_questions(csv_path: Path) -> List[Question]:
    """Load and validate questions. Reports all malformed rows together."""
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    if not csv_path.is_file():
        raise ValueError(f"The supplied path is not a file: {csv_path}")

    questions: List[Question] = []
    problems: List[str] = []

    try:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            if not reader.fieldnames:
                raise ValueError("The CSV file is empty or has no header row.")

            normalized_headers = {normalize_header(name) for name in reader.fieldnames if name}
            required_groups = [
                ("question", {"question", "q"}),
                ("option A", {"a", "option_a"}),
                ("option B", {"b", "option_b"}),
                ("option C", {"c", "option_c"}),
                ("option D", {"d", "option_d"}),
                ("answer", {"answer", "correct", "correct_answer", "ans"}),
            ]
            for label, aliases in required_groups:
                if not normalized_headers.intersection(aliases):
                    problems.append(f"Missing required CSV column for {label}.")

            if problems:
                raise ValueError("\n".join(problems))

            for row_number, row in enumerate(reader, start=2):
                if not any(str(value or "").strip() for value in row.values()):
                    continue  # Ignore completely blank rows.

                question_text = get_field(row, "question", "q")
                options = {
                    "A": get_field(row, "a", "option_a"),
                    "B": get_field(row, "b", "option_b"),
                    "C": get_field(row, "c", "option_c"),
                    "D": get_field(row, "d", "option_d"),
                }
                raw_answer = get_field(
                    row, "answer", "correct", "correct_answer", "ans"
                )

                row_problems = []
                if not question_text:
                    row_problems.append("question is blank")
                for letter, option_text in options.items():
                    if not option_text:
                        row_problems.append(f"option {letter} is blank")
                correct_letter = answer_to_letter(raw_answer, options)
                if not raw_answer:
                    row_problems.append("answer is blank")
                elif correct_letter is None:
                    row_problems.append(
                        "answer must be A/B/C/D or exactly match one option"
                    )

                if row_problems:
                    problems.append(
                        f"CSV row {row_number}: " + "; ".join(row_problems)
                    )
                    continue

                questions.append(
                    Question(
                        question=question_text,
                        options=options,
                        answer=correct_letter or "A",
                        subject=get_field(row, "subject", "category") or "Unspecified",
                        topic=get_field(row, "topic", "chapter") or "Unspecified",
                        difficulty=get_field(row, "difficulty", "level") or "Unspecified",
                        explanation=get_field(
                            row, "explanation", "reason", "solution", "rationale"
                        ),
                        source_row=row_number,
                    )
                )

    except UnicodeDecodeError as exc:
        raise ValueError(
            "Could not read this CSV as UTF-8. Save it as UTF-8 and try again."
        ) from exc
    except csv.Error as exc:
        raise ValueError(f"CSV formatting error: {exc}") from exc

    if problems:
        details = "\n".join(f"  - {problem}" for problem in problems)
        raise ValueError("The CSV has invalid data:\n" + details)
    if not questions:
        raise ValueError("No usable questions were found in the CSV file.")

    return questions


def ask_yes_no(prompt: str, default: bool = True) -> bool:
    """Ask a yes/no question. Enter accepts the displayed default."""
    suffix = "Y/n" if default else "y/N"
    while True:
        answer = input(f"{prompt} ({suffix}): ").strip().lower()
        if not answer:
            return default
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("Please enter Y or N.")


def choose_filter(label: str, values: Iterable[str]) -> str:
    """Let the user select one value or keep all values."""
    choices = sorted({value for value in values if value and value != "Unspecified"})
    if not choices:
        return "All"

    print(f"\n{label} filter:")
    print("  0) All")
    for index, value in enumerate(choices, start=1):
        print(f"  {index}) {value}")

    while True:
        response = input("Choose a number (Enter for All): ").strip()
        if not response or response == "0":
            return "All"
        if response.isdigit() and 1 <= int(response) <= len(choices):
            return choices[int(response) - 1]
        print("That selection is not in the list. Try again.")


def ask_question_count(available: int) -> int:
    """Ask how many questions to include in the test."""
    while True:
        response = input(
            f"Number of questions (1-{available}, Enter for all): "
        ).strip()
        if not response:
            return available
        try:
            count = int(response)
            if 1 <= count <= available:
                return count
        except ValueError:
            pass
        print(f"Enter a whole number from 1 to {available}.")


def ask_penalty() -> float:
    """Ask for the deduction per wrong answer, from 0 to 1 mark."""
    while True:
        response = input(
            "Negative marking per wrong answer (0 to 1, Enter for 0): "
        ).strip()
        if not response:
            return 0.0
        try:
            penalty = float(response)
            if 0 <= penalty <= 1:
                return penalty
        except ValueError:
            pass
        print("Enter a number between 0 and 1, such as 0.25, or press Enter.")


def run_test(questions: List[Question], negative_penalty: float) -> Tuple[List[dict], float]:
    """Run the MCQ test and return answer records and elapsed seconds."""
    results: List[dict] = []
    start_time = time.perf_counter()

    print("\n" + "=" * 64)
    print("                         TEST STARTED")
    print("Enter A, B, C or D. Enter S to skip a question.")
    print("=" * 64)

    for index, question in enumerate(questions, start=1):
        print(f"\nQuestion {index}/{len(questions)}")
        if question.subject != "Unspecified" or question.topic != "Unspecified":
            print(f"Subject: {question.subject}  |  Topic: {question.topic}")
        if question.difficulty != "Unspecified":
            print(f"Difficulty: {question.difficulty}")
        print(f"\n{question.question}")
        for letter in OPTIONS:
            print(f"  {letter}) {question.options[letter]}")

        question_start = time.perf_counter()
        while True:
            choice = input("Your answer (A/B/C/D, or S to skip): ").strip().upper()
            if choice in OPTIONS or choice == "S":
                break
            print("Invalid input. Please enter A, B, C, D or S.")
        question_seconds = time.perf_counter() - question_start

        if choice == "S":
            status = "SKIPPED"
            user_answer = ""
            marks = 0.0
        elif choice == question.answer:
            status = "CORRECT"
            user_answer = choice
            marks = 1.0
        else:
            status = "WRONG"
            user_answer = choice
            marks = -negative_penalty

        results.append(
            {
                "number": index,
                "question": question.question,
                "subject": question.subject,
                "topic": question.topic,
                "difficulty": question.difficulty,
                "user_answer": user_answer,
                "user_option": question.options.get(user_answer, "Not answered"),
                "correct_answer": question.answer,
                "correct_option": question.options[question.answer],
                "status": status,
                "marks": marks,
                "explanation": question.explanation,
                "time_seconds": round(question_seconds, 2),
            }
        )

    return results, time.perf_counter() - start_time


def grouped_stats(results: List[dict], field: str) -> List[Tuple[str, int, int, int, float]]:
    """Return (group, total, correct, attempted, accuracy) statistics."""
    groups = defaultdict(lambda: {"total": 0, "correct": 0, "attempted": 0})
    for item in results:
        name = item.get(field) or "Unspecified"
        groups[name]["total"] += 1
        if item["status"] != "SKIPPED":
            groups[name]["attempted"] += 1
        if item["status"] == "CORRECT":
            groups[name]["correct"] += 1

    output = []
    for name, data in sorted(groups.items()):
        accuracy = (
            data["correct"] / data["attempted"] * 100
            if data["attempted"]
            else 0.0
        )
        output.append(
            (name, data["total"], data["correct"], data["attempted"], accuracy)
        )
    return output


def print_group_analysis(title: str, results: List[dict], field: str) -> None:
    """Display subject-wise or topic-wise performance."""
    print(f"\n{title}")
    print("-" * 64)
    stats = grouped_stats(results, field)
    if not stats:
        print("No analysis data available.")
        return
    for name, total, correct, attempted, accuracy in stats:
        print(
            f"{name:<24} Correct: {correct}/{total}  "
            f"Attempted: {attempted}  Accuracy: {accuracy:.1f}%"
        )


def build_summary(results: List[dict], elapsed: float, penalty: float) -> dict:
    """Calculate totals and overall performance metrics."""
    total = len(results)
    correct = sum(item["status"] == "CORRECT" for item in results)
    wrong = sum(item["status"] == "WRONG" for item in results)
    skipped = sum(item["status"] == "SKIPPED" for item in results)
    attempted = correct + wrong
    net_score = correct - wrong * penalty
    score_percent = net_score / total * 100 if total else 0.0
    accuracy = correct / attempted * 100 if attempted else 0.0
    return {
        "total": total,
        "correct": correct,
        "wrong": wrong,
        "skipped": skipped,
        "attempted": attempted,
        "net_score": net_score,
        "score_percent": score_percent,
        "accuracy_percent": accuracy,
        "duration_seconds": elapsed,
    }


def print_summary(results: List[dict], summary: dict, penalty: float) -> None:
    """Print score, accuracy, topic analysis and answer review."""
    print("\n" + "=" * 64)
    print("                         TEST RESULT")
    print("=" * 64)
    print(f"Questions             : {summary['total']}")
    print(f"Correct               : {summary['correct']}")
    print(f"Wrong                 : {summary['wrong']}")
    print(f"Skipped               : {summary['skipped']}")
    print(f"Negative marking      : {penalty:.2f} per wrong answer")
    print(f"Net score             : {summary['net_score']:.2f}/{summary['total']}")
    print(f"Score percentage      : {summary['score_percent']:.1f}%")
    print(f"Accuracy (attempted)  : {summary['accuracy_percent']:.1f}%")
    print(f"Time taken            : {summary['duration_seconds']:.1f} seconds")

    print_group_analysis("SUBJECT-WISE ANALYSIS", results, "subject")
    print_group_analysis("TOPIC-WISE ANALYSIS", results, "topic")

    weak_topics = [
        row for row in grouped_stats(results, "topic")
        if row[3] > 0 and row[4] < 60
    ]
    print("\nREVISION SUGGESTIONS")
    print("-" * 64)
    if weak_topics:
        for topic, total, correct, attempted, accuracy in weak_topics:
            print(f"Revise: {topic} ({accuracy:.1f}% accuracy, {attempted} attempted)")
    else:
        print("No topic fell below 60% accuracy in this attempt.")

    print("\nANSWER REVIEW")
    print("-" * 64)
    for item in results:
        print(f"Q{item['number']} [{item['status']}]: {item['question']}")
        print(f"  Your answer   : {item['user_answer'] or 'Skipped'} "
              f"{item['user_option'] if item['user_answer'] else ''}")
        print(f"  Correct answer: {item['correct_answer']} - {item['correct_option']}")
        if item["explanation"]:
            print(f"  Explanation   : {item['explanation']}")
        print()


def save_reports(
    results: List[dict],
    summary: dict,
    quiz_path: Path,
    subject_filter: str,
    difficulty_filter: str,
) -> Tuple[Path, Path]:
    """Save detailed question results and append one row to test history."""
    base_dir = Path(__file__).resolve().parent
    reports_dir = base_dir / "reports"
    reports_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    detail_path = reports_dir / f"attempt_{timestamp}.csv"
    history_path = base_dir / "test_history.csv"

    detail_fields = [
        "number", "question", "subject", "topic", "difficulty",
        "user_answer", "user_option", "correct_answer", "correct_option",
        "status", "marks", "explanation", "time_seconds",
    ]
    with detail_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=detail_fields)
        writer.writeheader()
        writer.writerows(results)

    history_row = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "quiz_file": quiz_path.name,
        "subject_filter": subject_filter,
        "difficulty_filter": difficulty_filter,
        "total_questions": summary["total"],
        "correct": summary["correct"],
        "wrong": summary["wrong"],
        "skipped": summary["skipped"],
        "net_score": f"{summary['net_score']:.2f}",
        "score_percent": f"{summary['score_percent']:.2f}",
        "accuracy_percent": f"{summary['accuracy_percent']:.2f}",
        "duration_seconds": f"{summary['duration_seconds']:.2f}",
        "report_file": str(detail_path.relative_to(base_dir)),
    }
    write_header = not history_path.exists() or history_path.stat().st_size == 0
    with history_path.open("a", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=HISTORY_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(history_row)

    return detail_path, history_path


def show_history() -> None:
    """Display the latest saved test attempts."""
    history_path = Path(__file__).resolve().parent / "test_history.csv"
    if not history_path.exists():
        print("No saved test history yet. Complete a test first.")
        return

    try:
        with history_path.open("r", encoding="utf-8-sig", newline="") as file:
            rows = list(csv.DictReader(file))
    except (OSError, csv.Error) as exc:
        print(f"Could not read test history: {exc}")
        return

    if not rows:
        print("No saved test history yet. Complete a test first.")
        return

    print("\nLATEST TEST ATTEMPTS")
    print("-" * 80)
    for row in reversed(rows[-10:]):
        print(
            f"{row.get('timestamp', 'Unknown date')} | "
            f"{row.get('quiz_file', 'Unknown file')} | "
            f"Score: {row.get('score_percent', '0')}% | "
            f"Accuracy: {row.get('accuracy_percent', '0')}% | "
            f"Correct: {row.get('correct', '0')}/{row.get('total_questions', '0')}"
        )
    print("\nShowing up to the 10 most recent attempts.")


def resolve_csv_path(raw_path: str, base_dir: Path) -> Path:
    """Resolve quoted, absolute, or script-relative CSV paths."""
    cleaned = raw_path.strip().strip('"').strip("'")
    path = Path(cleaned).expanduser()
    if not path.is_absolute():
        script_relative = base_dir / path
        if script_relative.exists():
            path = script_relative
        else:
            path = Path.cwd() / path
    return path.resolve()


def start_test(base_dir: Path) -> None:
    """Load a CSV, configure a test, run it, analyze and save the results."""
    print("\nSTART A NEW TEST")
    default_csv = base_dir / "sample_questions.csv"
    raw_path = input(
        f"CSV file path (Enter for {default_csv.name}): "
    ).strip()
    quiz_path = resolve_csv_path(raw_path or str(default_csv), base_dir)

    try:
        all_questions = load_questions(quiz_path)
    except (OSError, ValueError) as exc:
        print(f"\nCould not load questions:\n{exc}")
        return

    print(f"\nLoaded and validated {len(all_questions)} questions from {quiz_path.name}.")
    subject_filter = choose_filter("Subject", (q.subject for q in all_questions))
    filtered = [
        q for q in all_questions
        if subject_filter == "All" or q.subject == subject_filter
    ]
    difficulty_filter = choose_filter("Difficulty", (q.difficulty for q in filtered))
    filtered = [
        q for q in filtered
        if difficulty_filter == "All" or q.difficulty == difficulty_filter
    ]

    if not filtered:
        print("No questions match the selected filters.")
        return

    count = ask_question_count(len(filtered))
    selected = filtered[:]
    if ask_yes_no("Randomize question order", default=True):
        random.shuffle(selected)
    selected = selected[:count]
    penalty = ask_penalty()

    try:
        results, elapsed = run_test(selected, penalty)
    except (KeyboardInterrupt, EOFError):
        print("\nTest interrupted. This incomplete attempt was not saved.")
        return

    summary = build_summary(results, elapsed, penalty)
    print_summary(results, summary, penalty)

    try:
        detail_path, history_path = save_reports(
            results, summary, quiz_path, subject_filter, difficulty_filter
        )
        print("\nREPORTS SAVED")
        print(f"Detailed answer report: {detail_path}")
        print(f"Performance history   : {history_path}")
    except OSError as exc:
        print(f"\nThe test finished, but its report could not be saved: {exc}")


def main() -> None:
    """Display the application menu."""
    base_dir = Path(__file__).resolve().parent
    print("\n" + "=" * 64)
    print("              PYTHON TEST & STUDY ANALYZER 2.0")
    print("=" * 64)

    while True:
        print("\nMAIN MENU")
        print("1. Start a new test")
        print("2. View performance history")
        print("3. Exit")
        choice = input("Choose an option (1-3): ").strip()

        if choice == "1":
            start_test(base_dir)
        elif choice == "2":
            show_history()
        elif choice == "3":
            print("Thank you for using Test & Study Analyzer 2.0.")
            break
        else:
            print("Invalid choice. Please select 1, 2 or 3.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nProgram closed.")
        sys.exit(0)
