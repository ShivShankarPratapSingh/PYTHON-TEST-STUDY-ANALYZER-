PYTHON TEST & STUDY ANALYZER 2.0
================================

FILES
-----
TEST_STUDY_ANALYZER_2.py : Main application
sample_questions.csv     : Sample question bank

REQUIREMENTS
------------
- Python 3.9 or later recommended
- No third-party packages required

RUN ON WINDOWS
--------------
1. Keep the Python file and CSV file in the same folder.
2. Open Command Prompt in that folder.
3. Run:

   py TEST_STUDY_ANALYZER_2.py

4. Select 1 to start a test, 2 to view history, or 3 to exit.

CSV FORMAT
----------
Required columns:
question, option_a, option_b, option_c, option_d, answer

Optional columns:
subject, topic, difficulty, explanation

The original program's common header names are also supported, including:
question or q; a/option_a/option a; b/option_b/option b;
c/option_c/option c; d/option_d/option d;
answer/correct/correct_answer/ans.

The answer can be A, B, C, D, or exactly match one option's text.

FEATURES IN VERSION 2.0
-----------------------
- Validates question rows and answer keys before the test starts.
- Filters questions by subject and difficulty.
- Lets the user choose the number of questions.
- Can randomize question order.
- Supports skipped questions.
- Optional negative marking from 0 to 1 mark per wrong answer.
- Calculates net score, score percentage and attempted-answer accuracy.
- Displays subject-wise and topic-wise performance.
- Suggests topics below 60% accuracy for revision.
- Shows answer review and optional explanations.
- Saves each attempt's detailed answers in the reports folder.
- Appends test summaries to test_history.csv.
- Shows up to the 10 most recent attempts from the history file.

OUTPUT FILES
------------
After a completed test, the program creates:
- reports/attempt_YYYYMMDD_HHMMSS.csv
- test_history.csv

NOTES
-----
- A skipped question is not counted as attempted for accuracy.
- A skipped question receives zero marks.
- Each correct answer gives 1 mark.
- Each wrong answer deducts the selected negative-marking value.
- The score percentage is net marks divided by the total number of questions.
- The time shown is elapsed test time; there is no countdown timer in this version.
