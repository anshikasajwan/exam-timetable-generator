# AI Exam Timetable Generator (DAA - Graph Colouring)

Generates a clash-free exam timetable for many programmes, semesters and sections.

## Rules enforced
1. A class never has two exams on the same day.
2. A course shared by many sections/classes has **one** exam date for all of them.
3. Uses as few exam days as the algorithm can find; skips chosen weekdays and holidays; optional study-gap days.

## Run the web UI (recommended)
```
python server.py
```
Your browser opens at http://localhost:8000 (no packages to install, only Python 3).
1. Upload your dataset as a CSV (or paste it, or press "Load sample").
2. Set start date, days off, holidays, study gap and algorithm.
3. Press **Generate timetable**. Browse the Day-wise, Class grid, Class-wise and Algorithms tabs, then download CSVs or print.

### Dataset format
One row per class-course pair. A "class" = programme + semester + section.
```
class,course_code,course_name
CSE-Sem1-A,MA101,Engineering Calculus
CSE-Sem1-B,MA101,Engineering Calculus
CSE-Sem3-A,CS201,Data Structures
```
* Required columns: `class` and `course_code`; `course_name` is optional.
* Header names like `section`, `subject_code`, `subject_name` also work. Comma, semicolon or tab separated.
* In Excel use File > Save As > CSV. Course codes are upper-cased automatically so `cs201` and `CS201` are one course.

## Command line (optional)
```
python main.py --compare             # DSATUR vs Welsh-Powell vs Backtracking on sample_data.json
python main.py --algo backtracking --timeout 20
```

## Files
| File | Purpose |
|---|---|
| `scheduler.py` | All algorithms: conflict graph, Welsh-Powell, DSATUR, backtracking, date mapping, validation |
| `server.py` | Local web server + CSV import + JSON API |
| `index.html` | The user interface |
| `main.py` | Command-line version |
| `sample_dataset.csv`, `sample_data.json` | Demo data |

## DAA concepts
| Step | Technique | Complexity |
|---|---|---|
| Build conflict graph | Adjacency sets; every pair of courses inside a class becomes an edge | O(sum of s^2) |
| Welsh-Powell | Greedy colouring, vertices by decreasing degree | O(V log V + E) |
| DSATUR | Greedy, pick vertex with highest saturation degree | O(V^2) |
| Backtracking | Exact m-colouring with symmetry breaking + time limit | O(k^V) worst case |

* Graph colouring is **NP-hard**: greedy is fast but not always optimal, backtracking is optimal but exponential.
* Lower bound on exam days = the largest number of courses in one class (they form a clique).
* Colour = exam day, vertex = course, edge = "some class writes both".

## Ideas to extend
Room capacity per day, two slots per day, exam-gap penalty, invigilator clashes.
