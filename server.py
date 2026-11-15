"""
Local web server for the Exam Timetable Generator (no external packages needed).

    python server.py            -> opens http://localhost:8000 in your browser

Dataset format (CSV, one row per class-course pair):
    class,course_code,course_name
    CSE-Sem1-A,MA101,Engineering Calculus
"""
import argparse
import csv
import io
import json
import os
import sys
import threading
import webbrowser
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import scheduler as S

BASE = os.path.dirname(os.path.abspath(__file__))

CLASS_HEADERS = ("class", "section", "class name", "class_name", "classname", "group")
CODE_HEADERS = ("course_code", "course code", "coursecode", "code", "subject_code",
                "subject code", "subjectcode")
NAME_HEADERS = ("course_name", "course name", "coursename", "name", "subject_name",
                "subject name", "subjectname", "title")
LOOSE_CODE_HEADERS = ("course", "subject")


# ---------------------------------------------------------------- dataset parsing
def parse_dataset(text):
    """CSV text -> (classes {class: [codes]}, names {code: name})."""
    text = text.lstrip("﻿")
    try:
        dialect = csv.Sniffer().sniff(text[:2000], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = [r for r in csv.reader(io.StringIO(text), dialect) if any(c.strip() for c in r)]
    if not rows:
        raise ValueError("The dataset is empty.")
    header = [h.strip().lower() for h in rows[0]]

    def find(options, exclude=()):
        for i, h in enumerate(header):
            if h in options and i not in exclude:
                return i
        return None

    ci = find(CLASS_HEADERS)
    ki = find(CODE_HEADERS)
    if ki is None:
        ki = find(LOOSE_CODE_HEADERS)
    ni = find(NAME_HEADERS, exclude=(ki,))
    if ci is None or ki is None:
        raise ValueError("Could not find the required columns. The first row must be a header "
                         "containing at least 'class' and 'course_code' "
                         "(optional: 'course_name'). Found: " + ", ".join(header))

    classes, names = {}, {}
    for line_no, r in enumerate(rows[1:], start=2):
        if len(r) <= max(ci, ki):
            raise ValueError(f"Row {line_no} has too few columns: {r}")
        cls, code = r[ci].strip(), r[ki].strip().upper()
        if not cls or not code:
            continue
        lst = classes.setdefault(cls, [])
        if code not in lst:
            lst.append(code)
        if ni is not None and len(r) > ni and r[ni].strip():
            names.setdefault(code, r[ni].strip())
    if not classes:
        raise ValueError("No class/course rows found below the header.")
    return classes, names


def label(d):
    return d.strftime("%a %d %b %Y")


# --------------------------------------------------------------------- generation
def generate(p):
    classes, names = parse_dataset(p.get("csv", ""))
    adj = S.build_conflict_graph(classes)
    edges = sum(len(v) for v in adj.values()) // 2

    try:
        start = date.fromisoformat(p.get("start_date", ""))
    except ValueError:
        raise ValueError("Please choose a valid start date.")
    skip = [int(x) for x in p.get("skip_weekdays", [6])]
    if len(set(skip)) >= 7:
        raise ValueError("All weekdays are switched off - no exam day is available.")
    holidays = []
    for h in p.get("holidays", []):
        try:
            holidays.append(date.fromisoformat(h))
        except ValueError:
            raise ValueError(f"Holiday '{h}' is not a valid date (use YYYY-MM-DD).")
    gap = max(0, int(p.get("gap_days", 0)))
    timeout = max(1.0, min(float(p.get("timeout", 5)), 60.0))
    algo = p.get("algo", "dsatur")
    if algo not in S.ALGORITHMS:
        raise ValueError("Unknown algorithm.")
    max_days = p.get("max_days")

    results = {}
    for a in S.ALGORITHMS:
        results[a] = S.run(a, adj, classes, timeout)
    color, info = results[algo]

    dates = S.exam_dates(info["days"], start, skip, holidays, gap)
    date_of = {c: dates[k] for c, k in color.items()}
    errors = S.validate(classes, date_of)

    days = []
    for k in range(info["days"]):
        todays = sorted(c for c in color if color[c] == k)
        days.append({
            "day": k + 1, "date": dates[k].isoformat(), "label": label(dates[k]),
            "courses": [{"code": c, "name": names.get(c, ""),
                         "classes": [cl for cl, subs in classes.items() if c in subs]}
                        for c in todays]})
    by_class = {}
    for cl, subs in classes.items():
        by_class[cl] = [{"day": color[c] + 1, "label": label(date_of[c]),
                         "code": c, "name": names.get(c, "")}
                        for c in sorted(set(subs), key=lambda x: (date_of[x], x))]

    warnings = []
    if max_days not in (None, "", 0) and info["days"] > int(max_days):
        warnings.append(f"This timetable needs {info['days']} exam days but your limit is "
                        f"{int(max_days)}. Reduce gap days, enable more weekdays or merge exams.")
    lower = max((len(set(s)) for s in classes.values()), default=0)

    return {
        "summary": {"courses": len(adj), "conflicts": edges, "classes": len(classes),
                    "days": info["days"], "lower_bound": lower,
                    "first": dates[0].isoformat(), "last": dates[-1].isoformat()},
        "algo": algo,
        "comparison": [{"algo": a, "days": results[a][1]["days"],
                        "ms": round(results[a][1]["ms"], 3),
                        "proven": results[a][1]["proven_optimal"]} for a in S.ALGORITHMS],
        "days": days, "classes": by_class, "errors": errors, "warnings": warnings,
    }


# ------------------------------------------------------------------------- server
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _file(self, name, ctype):
        try:
            with open(os.path.join(BASE, name), "rb") as f:
                self._send(200, f.read(), ctype)
        except FileNotFoundError:
            self._send(404, json.dumps({"error": f"{name} not found next to server.py"}))

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            self._file("index.html", "text/html; charset=utf-8")
        elif path == "/api/sample":
            self._file("sample_dataset.csv", "text/csv; charset=utf-8")
        else:
            self._send(404, json.dumps({"error": "Not found"}))

    def do_POST(self):
        if self.path != "/api/generate":
            return self._send(404, json.dumps({"error": "Not found"}))
        try:
            n = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(n) or b"{}")
            self._send(200, json.dumps(generate(payload)))
        except (ValueError, KeyError, TypeError) as e:
            self._send(400, json.dumps({"error": str(e)}))
        except Exception as e:  # keep the server alive on unexpected errors
            self._send(500, json.dumps({"error": f"Unexpected error: {e}"}))


def main():
    ap = argparse.ArgumentParser(description="Exam Timetable Generator - web UI")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    server = None
    for port in range(a.port, a.port + 20):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
            break
        except OSError:
            continue
    if server is None:
        sys.exit("No free port found.")
    url = f"http://localhost:{server.server_address[1]}"
    print(f"Exam Timetable Generator running at {url}  (press Ctrl+C to stop)")
    if not a.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
