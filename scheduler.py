"""
Exam timetable scheduler built on GRAPH COLORING (DAA project).

Model
-----
* Every distinct COURSE is one vertex (a course taught in many sections is still
  ONE vertex, so it automatically gets ONE exam date for every section).
* Two courses are joined by an edge if at least one CLASS (programme + semester +
  section) has to write both of them.
* A colour = an exam day. Adjacent vertices must get different colours, so no class
  ever has two exams on the same day.
* Minimising the number of colours = minimising the length of the exam period.
"""
import time
from datetime import timedelta


# ---------------------------------------------------------------- graph building
def build_conflict_graph(classes):
    """classes: {class_name: [course, ...]} -> adjacency {course: set(courses)}.
    Time: O(sum of s^2) where s = courses per class."""
    adj = {}
    for subjects in classes.values():
        subjects = list(dict.fromkeys(subjects))          # drop duplicates, keep order
        for c in subjects:
            adj.setdefault(c, set())
        for i, a in enumerate(subjects):
            for b in subjects[i + 1:]:
                adj[a].add(b)
                adj[b].add(a)
    return adj


def num_colors(color):
    return max(color.values()) + 1 if color else 0


# ------------------------------------------------------------- algorithm 1: greedy
def welsh_powell(adj):
    """Greedy colouring in decreasing-degree order. O(V log V + E)."""
    order = sorted(adj, key=lambda v: (-len(adj[v]), v))
    color = {}
    for v in order:
        used = {color[u] for u in adj[v] if u in color}
        c = 0
        while c in used:
            c += 1
        color[v] = c
    return color


# ------------------------------------------------------------ algorithm 2: DSATUR
def dsatur(adj):
    """Brelaz's DSATUR: always colour the vertex whose neighbours already use the most
    distinct colours (ties -> highest degree). Optimal on bipartite graphs and usually
    much better than plain greedy. O(V^2)."""
    color = {}
    sat = {v: set() for v in adj}
    uncolored = set(adj)
    while uncolored:
        v = max(uncolored, key=lambda x: (len(sat[x]), len(adj[x]), x))
        c = 0
        while c in sat[v]:
            c += 1
        color[v] = c
        uncolored.discard(v)
        for u in adj[v]:
            sat[u].add(c)
    return color


# ------------------------------------------ algorithm 3: backtracking (exact, B&B)
def _k_colorable(adj, k, deadline):
    order = sorted(adj, key=lambda v: (-len(adj[v]), v))
    color = {}

    def solve(i, used):
        if time.perf_counter() > deadline:
            raise TimeoutError
        if i == len(order):
            return True
        v = order[i]
        forbidden = {color[u] for u in adj[v] if u in color}
        # symmetry breaking: never open more than one new colour at a time
        for c in range(min(used + 1, k)):
            if c in forbidden:
                continue
            color[v] = c
            if solve(i + 1, max(used, c + 1)):
                return True
            del color[v]
        return False

    return dict(color) if solve(0, 0) else None


def backtracking(adj, classes, timeout=10.0):
    """Start from DSATUR's answer (upper bound) and try to prove k-1 colours possible.
    Lower bound = largest number of courses in any single class (that set is a clique).
    Exponential worst case (graph colouring is NP-hard) so it is time-limited.
    Returns (colouring, proven_optimal)."""
    best = dsatur(adj)
    lb = max((len(set(s)) for s in classes.values()), default=0)
    deadline = time.perf_counter() + timeout
    k = num_colors(best) - 1
    try:
        while k >= max(lb, 1):
            found = _k_colorable(adj, k, deadline)
            if found is None:
                return best, True        # k impossible -> best is optimal
            best = found
            k = num_colors(best) - 1
        return best, True                # reached the lower bound
    except TimeoutError:
        return best, False


ALGORITHMS = ("dsatur", "welsh-powell", "backtracking")


def run(algo, adj, classes, timeout=10.0):
    t = time.perf_counter()
    proven = None
    if algo == "dsatur":
        col = dsatur(adj)
    elif algo == "welsh-powell":
        col = welsh_powell(adj)
    elif algo == "backtracking":
        col, proven = backtracking(adj, classes, timeout)
    else:
        raise ValueError(f"unknown algorithm {algo}")
    return col, {"algo": algo, "days": num_colors(col),
                 "ms": (time.perf_counter() - t) * 1000, "proven_optimal": proven}


# ------------------------------------------------------------------- calendar
def exam_dates(n_days, start, skip_weekdays=(6,), holidays=(), gap_days=0):
    """Turn colour 0..n-1 into real dates. Skips weekdays (0=Mon .. 6=Sun) and holidays;
    gap_days = free working days left between consecutive exam days (study leave)."""
    holidays = set(holidays)
    valid, d = [], start
    while len(valid) < n_days * (gap_days + 1):
        if d.weekday() not in skip_weekdays and d not in holidays:
            valid.append(d)
        d += timedelta(days=1)
    return [valid[i * (gap_days + 1)] for i in range(n_days)]


# ----------------------------------------------------------------- validation
def validate(classes, date_of):
    """Return list of rule violations (empty list = timetable is correct)."""
    errors = []
    for cls, subjects in classes.items():
        seen = {}
        for c in subjects:
            d = date_of[c]
            if d in seen:
                errors.append(f"{cls}: {seen[d]} and {c} both on {d}")
            seen[d] = c
    return errors
