"""Bounded rectangular furniture placement using real CP-SAT constraints."""
from __future__ import annotations

import math
from ortools.sat.python import cp_model


def integer(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > 1000000:
        raise ValueError(f"{name} must be an integer in [{minimum}, 1000000], unit mm")
    return value


def optimize_layout(spec: dict) -> dict:
    supported = {"width", "height", "clearance", "items", "obstacles"}
    unsupported = set(spec) - supported
    if unsupported:
        raise ValueError("Unsupported layout constraints: " + ", ".join(sorted(unsupported)) +
                         ". This solver requires a rectangular room and axis-aligned rectangular obstacles; constraints cannot be ignored.")
    width = integer(spec.get("width"), "width", 1)
    height = integer(spec.get("height"), "height", 1)
    clearance = integer(spec.get("clearance", 0), "clearance")
    items = spec.get("items", [])
    obstacles = spec.get("obstacles", [])
    if not isinstance(items, list) or not 1 <= len(items) <= 100 or not isinstance(obstacles, list) or len(obstacles) > 100:
        raise ValueError("items needs 1..100 rectangles; obstacles at most 100")
    model = cp_model.CpModel()
    xs, ys, rectangles = [], [], []
    used = set()
    for index, item in enumerate(items):
        if set(item) - {"id", "width", "height", "x", "y"}:
            raise ValueError("Unsupported item constraint (including rotation); axis-aligned fixed-size rectangles only")
        name = item.get("id")
        if not isinstance(name, str) or not name or name in used:
            raise ValueError("Each item requires a distinct nonempty id")
        used.add(name)
        w, h = integer(item.get("width"), name + ".width", 1), integer(item.get("height"), name + ".height", 1)
        if w + 2 * clearance > width or h + 2 * clearance > height:
            return {"ok": False, "status": "INFEASIBLE", "reason": f"{name} does not fit with boundary clearance"}
        x = model.new_int_var(clearance, width - w - clearance, name + "_x")
        y = model.new_int_var(clearance, height - h - clearance, name + "_y")
        for key, var in (("x", x), ("y", y)):
            if key in item:
                model.add(var == integer(item[key], name + "." + key))
        xs.append(x)
        ys.append(y)
        rectangles.append((x, y, w, h, name))
    for index, obstacle in enumerate(obstacles):
        if set(obstacle) - {"id", "x", "y", "width", "height"}:
            raise ValueError("Unsupported obstacle geometry; provide axis-aligned rectangles")
        x, y, w, h = (integer(obstacle.get(k), f"obstacles[{index}].{k}", 1 if k in {"width", "height"} else 0)
                       for k in ("x", "y", "width", "height"))
        if x + w > width or y + h > height:
            raise ValueError("Obstacle must be inside the room")
        rectangles.append((x, y, w, h, f"obstacle_{index}"))
    for i, a in enumerate(rectangles):
        for j in range(i + 1, len(rectangles)):
            if i >= len(items):
                continue  # Existing obstacles may overlap each other.
            b = rectangles[j]
            choices = [model.new_bool_var(f"sep_{i}_{j}_{k}") for k in range(4)]
            model.add(a[0] + a[2] + clearance <= b[0]).only_enforce_if(choices[0])
            model.add(b[0] + b[2] + clearance <= a[0]).only_enforce_if(choices[1])
            model.add(a[1] + a[3] + clearance <= b[1]).only_enforce_if(choices[2])
            model.add(b[1] + b[3] + clearance <= a[1]).only_enforce_if(choices[3])
            model.add_bool_or(choices)
    model.minimize(sum(xs) + sum(ys))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 5
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    status = solver.solve(model)
    success = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    return {"ok": success, "status": solver.status_name(status), "units": "mm",
            "items": [{"id": r[4], "x": solver.value(r[0]), "y": solver.value(r[1]),
                       "width": r[2], "height": r[3]} for r in rectangles[:len(items)]] if success else [],
            "scope": "Axis-aligned rectangles, no rotation; user-specified clearance, not code compliance or circulation design"}
