"""CLI for the exam timetable generator.   python main.py --help"""
import argparse
import csv
import html
import json
import os
import sys
from datetime import date

import scheduler as S


def load(path):
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["start"] = date.fromisoformat(cfg["start_date"])
    cfg["holiday_set"] = [date.fromisoformat(h) for h in cfg.get("holidays", [])]
    cfg.setdefault("courses", {})
    cfg.setdefault("skip_weekdays", [6])
    cfg.setdefault("gap_days", 0)
    return cfg


def fmt(d):
    return d.strftime("%a %d-%b-%Y")


def write_outputs(cfg, color, date_of, outdir):
    names = cfg["courses"]
    classes = cfg["classes"]
    os.makedirs(outdir, exist_ok=True)

    # 1. master timetable (one row per course)
    master = sorted(color, key=lambda c: (date_of[c], c))
    p1 = os.path.join(outdir, "timetable_master.csv")
    with open(p1, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Exam Day", "Date", "Course Code", "Course Name", "Classes Writing"])
        for c in master:
            who = [k for k, v in classes.items() if c in v]
            w.writerow([color[c] + 1, fmt(date_of[c]), c, names.get(c, ""), "; ".join(who)])

    # 2. class-wise timetable
    p2 = os.path.join(outdir, "timetable_by_class.csv")
    with open(p2, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Class", "Date", "Course Code", "Course Name"])
        for cls, subs in classes.items():
            for c in sorted(set(subs), key=lambda x: date_of[x]):
                w.writerow([cls, fmt(date_of[c]), c, names.get(c, "")])

    # 3. printable HTML
    p3 = os.path.join(outdir, "timetable.html")
    h = ["<!doctype html><meta charset='utf-8'><title>Exam Timetable</title>",
         "<style>body{font-family:system-ui,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem}"
         "table{border-collapse:collapse;width:100%;margin-bottom:1.5rem}"
         "th,td{border:1px solid #ccc;padding:6px 10px;text-align:left}"
         "th{background:#f0f0f5}h2{margin-top:2rem}</style><h1>Exam Timetable</h1>",
         "<h2>Master schedule</h2><table><tr><th>Date</th><th>Course</th><th>Classes</th></tr>"]
    for c in master:
        who = ", ".join(k for k, v in classes.items() if c in v)
        h.append(f"<tr><td>{fmt(date_of[c])}</td><td>{html.escape(c)} &ndash; "
                 f"{html.escape(names.get(c, ''))}</td><td>{html.escape(who)}</td></tr>")
    h.append("</table><h2>Class-wise</h2>")
    for cls, subs in classes.items():
        h.append(f"<h3>{html.escape(cls)}</h3><table><tr><th>Date</th><th>Course</th></tr>")
        for c in sorted(set(subs), key=lambda x: date_of[x]):
            h.append(f"<tr><td>{fmt(date_of[c])}</td><td>{html.escape(c)} &ndash; "
                     f"{html.escape(names.get(c, ''))}</td></tr>")
        h.append("</table>")
    with open(p3, "w", encoding="utf-8") as f:
        f.write("".join(h))
    return [p1, p2, p3]


def main():
    ap = argparse.ArgumentParser(description="Exam timetable generator (graph colouring)")
    ap.add_argument("--input", default="sample_data.json")
    ap.add_argument("--algo", choices=S.ALGORITHMS, default="dsatur")
    ap.add_argument("--compare", action="store_true", help="run every algorithm and compare")
    ap.add_argument("--timeout", type=float, default=10.0, help="backtracking time limit (s)")
    ap.add_argument("--outdir", default="output")
    a = ap.parse_args()

    cfg = load(a.input)
    classes = cfg["classes"]
    adj = S.build_conflict_graph(classes)
    edges = sum(len(v) for v in adj.values()) // 2
    print(f"Courses (vertices): {len(adj)} | Conflicts (edges): {edges} | Classes: {len(classes)}")

    if a.compare:
        print(f"\n{'Algorithm':<14}{'Exam days':>10}{'Time (ms)':>12}  Optimal?")
        for algo in S.ALGORITHMS:
            _, info = S.run(algo, adj, classes, a.timeout)
            opt = {None: "-", True: "proven", False: "unknown (timeout)"}[info["proven_optimal"]]
            print(f"{algo:<14}{info['days']:>10}{info['ms']:>12.2f}  {opt}")

    color, info = S.run(a.algo, adj, classes, a.timeout)
    dates = S.exam_dates(info["days"], cfg["start"], cfg["skip_weekdays"],
                         cfg["holiday_set"], cfg["gap_days"])
    date_of = {c: dates[k] for c, k in color.items()}

    errors = S.validate(classes, date_of)
    print(f"\nUsing {a.algo}: {info['days']} exam days, {dates[0]} -> {dates[-1]}")
    if errors:
        print("INVALID TIMETABLE:\n  " + "\n  ".join(errors))
        sys.exit(1)
    print("Validation passed: no class has two exams on the same day; "
          "every course has exactly one date for all its sections.")
    if "max_days" in cfg and info["days"] > cfg["max_days"]:
        print(f"WARNING: needs {info['days']} days but only {cfg['max_days']} are allowed.")

    print("\nSchedule:")
    for k in range(info["days"]):
        todays = sorted(c for c in color if color[c] == k)
        print(f"  Day {k + 1:>2}  {fmt(dates[k])}: {', '.join(todays)}")
    for p in write_outputs(cfg, color, date_of, a.outdir):
        print("wrote", p)


if __name__ == "__main__":
    main()
