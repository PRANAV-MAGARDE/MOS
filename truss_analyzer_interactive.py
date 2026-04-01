"""
=============================================================
  2D TRUSS ANALYZER — Interactive Input Version
  Method of Joints  (ΣFx = 0,  ΣFy = 0  at every joint)
=============================================================
  Usage:
      python truss_analyzer_interactive.py

  The script will guide you through entering:
    1. Joint coordinates
    2. Members (connections between joints)
    3. Supports (pin or roller, with orientation)
    4. Applied loads (force + direction at joints)

  Output: truss_analysis_output.png saved in the same folder.
=============================================================
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import warnings
warnings.filterwarnings("ignore")


# ─────────────────────────────────────────────────────────────────────────────
#  TERMINAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def header(title):
    w = 62
    print("\n" + "═" * w)
    print(f"  {title}")
    print("═" * w)

def section(title):
    print(f"\n  ── {title} {'─'*(55-len(title))}")

def prompt(msg, default=None):
    suffix = f"  [{default}]" if default is not None else ""
    val = input(f"    {msg}{suffix}: ").strip()
    if val == "" and default is not None:
        return str(default)
    return val

def prompt_float(msg, default=None):
    while True:
        val = prompt(msg, default)
        try:
            return float(val)
        except ValueError:
            print(f"    ✗ Please enter a number.")

def prompt_int(msg, default=None):
    while True:
        val = prompt(msg, default)
        try:
            return int(val)
        except ValueError:
            print(f"    ✗ Please enter an integer.")

def prompt_choice(msg, choices, default=None):
    choices_lower = [c.lower() for c in choices]
    while True:
        val = prompt(f"{msg} ({'/'.join(choices)})", default)
        if val.lower() in choices_lower:
            return val.lower()
        print(f"    ✗ Choose one of: {', '.join(choices)}")

def yn(msg, default="y"):
    return prompt_choice(msg, ["y", "n"], default) == "y"


# ─────────────────────────────────────────────────────────────────────────────
#  INPUT COLLECTION
# ─────────────────────────────────────────────────────────────────────────────

def collect_joints():
    """Ask the user to enter joint coordinates one by one."""
    header("STEP 1 — DEFINE JOINTS")
    print("""
  Each joint is a node in the truss defined by its (x, y) position in metres.
  Label each joint with a name (e.g. A, B, C …).
  Press Enter after the last joint when done.
""")
    joints  = {}   # {id: (x, y)}
    labels  = {}   # {id: label}
    jid     = 0
    alpha   = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    while True:
        default_lbl = alpha[jid] if jid < len(alpha) else str(jid)
        section(f"Joint #{jid + 1}")
        lbl = prompt(f"Label", default_lbl)
        x   = prompt_float("x  (m)")
        y   = prompt_float("y  (m)")
        joints[jid]  = (x, y)
        labels[jid]  = lbl.upper()
        jid += 1
        if not yn("Add another joint?", "y"):
            break

    print(f"\n  ✓  {len(joints)} joint(s) defined.")
    return joints, labels


def collect_members(joints, labels):
    """Ask user which joints to connect with members."""
    header("STEP 2 — DEFINE MEMBERS")
    lbl_to_id = {v: k for k, v in labels.items()}
    joint_list = "  ".join(f"{labels[i]}({joints[i][0]},{joints[i][1]})" for i in joints)
    print(f"\n  Joints: {joint_list}")
    print("""
  Enter a member as two joint labels separated by a space or dash.
  Example:  A B   or  A-B
""")
    members = []

    while True:
        section(f"Member #{len(members) + 1}")
        raw = prompt("Joints (e.g. A B  or  A-B)")
        parts = raw.replace("-", " ").split()
        if len(parts) != 2:
            print("    ✗ Enter exactly two labels.")
            continue
        a, b = parts[0].upper(), parts[1].upper()
        if a not in lbl_to_id or b not in lbl_to_id:
            missing = [x for x in [a, b] if x not in lbl_to_id]
            print(f"    ✗ Unknown label(s): {', '.join(missing)}")
            continue
        ia, ib = lbl_to_id[a], lbl_to_id[b]
        if ia == ib:
            print("    ✗ A member cannot connect a joint to itself.")
            continue
        dup = any((m[0] == ia and m[1] == ib) or (m[0] == ib and m[1] == ia)
                  for m in members)
        if dup:
            print(f"    ✗ Member {a}–{b} already exists.")
        else:
            members.append((ia, ib))
            print(f"    ✓  Member {a}–{b} added.")

        if not yn("Add another member?", "y"):
            break

    print(f"\n  ✓  {len(members)} member(s) defined.")
    return members


def collect_supports(joints, labels):
    """
    Ask for support type, joint, and orientation for each support.

    Support types:
      pin    – restrains Fx and Fy  (2 reactions)
      roller – restrains only the reaction perpendicular to its rolling surface
               orientation: the angle (degrees) of the surface the roller sits on
               (0° = horizontal surface → only vertical Ry;
                90° = vertical surface → only horizontal Rx)

    For a statically determinate truss we need exactly 3 reaction unknowns:
      • 1 pin  + 1 roller (most common)
      • 3 rollers with suitable orientations
    """
    header("STEP 3 — DEFINE SUPPORTS")
    lbl_to_id = {v: k for k, v in labels.items()}
    print("""
  Supported joints resist movement. Each support contributes reaction forces.
  For a statically determinate truss you need exactly 3 reaction unknowns:
    ▸ 1 pin  (fixes X and Y)  +  1 roller (fixes Y, or another direction)
    ▸ or any combination totalling 3 unknowns.

  Roller orientation angle = angle of the SURFACE the roller rests on (degrees):
    0°  → horizontal surface → roller pushes vertically  (Ry only)
    90° → vertical surface   → roller pushes horizontally (Rx only)
""")
    supports = {}   # {jid: {"type": "pin"/"roller", "angle": float}}

    while True:
        section(f"Support #{len(supports) + 1}")
        lbl = prompt("Joint label").upper()
        if lbl not in lbl_to_id:
            print(f"    ✗ Unknown joint '{lbl}'.")
            continue
        jid = lbl_to_id[lbl]
        if jid in supports:
            print(f"    ✗ Joint {lbl} already has a support.")
            continue

        stype = prompt_choice("Type", ["pin", "roller"])
        angle = 0.0
        if stype == "roller":
            angle = prompt_float("Surface angle (deg, 0=horizontal)", 0)

        supports[jid] = {"type": stype, "angle": float(angle)}
        rcount = sum(2 if s["type"] == "pin" else 1 for s in supports.values())
        print(f"    ✓  {stype.capitalize()} support at {lbl}. "
              f"Total reaction unknowns so far: {rcount}")

        if rcount >= 3 and not yn("Add another support?", "n"):
            break
        elif rcount < 3:
            print(f"    ⚠  Need {3 - rcount} more reaction unknown(s).")
            if not yn("Continue adding supports?", "y"):
                break

    rcount = sum(2 if s["type"] == "pin" else 1 for s in supports.values())
    if rcount != 3:
        print(f"\n  ⚠  Warning: {rcount} reaction unknown(s) — "
              f"truss may not be statically determinate.")
    else:
        print(f"\n  ✓  {len(supports)} support(s) — 3 reaction unknowns. OK.")
    return supports


def collect_loads(joints, labels):
    """
    Ask for applied forces at joints.
    Each load is entered as magnitude + angle OR as Fx, Fy components.
    """
    header("STEP 4 — DEFINE APPLIED LOADS")
    lbl_to_id = {v: k for k, v in labels.items()}
    print("""
  Enter the external loads applied to the truss joints.
  You can specify each load as:
    (a) Fx and Fy components  (→ and ↑ positive, in kN)
    (b) Magnitude + angle     (angle measured from +x axis, CCW positive)

  Typical case: a downward load of 50 kN →  Fx = 0,  Fy = -50
""")
    loads = {}   # {jid: (Fx, Fy)} in Newtons

    while True:
        section(f"Load #{len(loads) + 1}")
        lbl = prompt("Joint label").upper()
        if lbl not in lbl_to_id:
            print(f"    ✗ Unknown joint '{lbl}'.")
            continue
        jid = lbl_to_id[lbl]

        entry = prompt_choice("Entry mode", ["components", "polar"], "components")
        if entry == "components":
            fx = prompt_float("Fx (kN, → positive)", 0) * 1e3
            fy = prompt_float("Fy (kN, ↑ positive)") * 1e3
        else:
            mag   = prompt_float("Magnitude (kN)") * 1e3
            angle = prompt_float("Angle (deg, 0=rightward, 90=upward)")
            fx = mag * np.cos(np.radians(angle))
            fy = mag * np.sin(np.radians(angle))

        if jid in loads:
            loads[jid] = (loads[jid][0] + fx, loads[jid][1] + fy)
            print(f"    ✓  Load added to {lbl} (cumulative).")
        else:
            loads[jid] = (fx, fy)
            print(f"    ✓  Load at {lbl}: "
                  f"Fx={fx/1e3:.2f} kN, Fy={fy/1e3:.2f} kN")

        if not yn("Add another load?", "y"):
            break

    print(f"\n  ✓  {len(loads)} loaded joint(s).")
    return loads


# ─────────────────────────────────────────────────────────────────────────────
#  SOLVER — REACTIONS
# ─────────────────────────────────────────────────────────────────────────────

def compute_reactions(joints, members, supports, loads):
    """
    Assemble and solve 3 global equilibrium equations.
    Supports dict:  {jid: {"type": "pin"/"roller", "angle": deg}}

    A roller at angle θ (surface angle) pushes perpendicular to the surface:
      reaction direction = (−sin θ, cos θ)
    A pin contributes two unknowns: Rx and Ry independently.
    """
    unknowns = []   # list of (jid, ux, uy)  — unit direction of reaction
    for jid, sup in supports.items():
        if sup["type"] == "pin":
            unknowns.append((jid, 1.0, 0.0))   # Rx
            unknowns.append((jid, 0.0, 1.0))   # Ry
        else:
            θ = np.radians(sup["angle"])
            unknowns.append((jid, -np.sin(θ), np.cos(θ)))

    if len(unknowns) != 3:
        raise ValueError(
            f"Need exactly 3 reaction unknowns, got {len(unknowns)}.")

    # Total applied load
    total_fx = sum(fx for fx, fy in loads.values())
    total_fy = sum(fy for fx, fy in loads.values())

    # Pivot: pin joint (or first support if no pin)
    pivot_jid = next(
        (jid for jid, s in supports.items() if s["type"] == "pin"),
        list(supports.keys())[0]
    )
    xp, yp = joints[pivot_jid]

    # Moment of applied loads about pivot (CCW +)
    M_loads = sum(
        (joints[jid][0] - xp) * fy - (joints[jid][1] - yp) * fx
        for jid, (fx, fy) in loads.items()
    )

    # Build 3×3:  row0=ΣFx, row1=ΣFy, row2=ΣM
    A = np.zeros((3, 3))
    b = np.array([-total_fx, -total_fy, -M_loads])

    for col, (jid, ux, uy) in enumerate(unknowns):
        xj, yj = joints[jid]
        A[0, col] = ux
        A[1, col] = uy
        A[2, col] = (xj - xp) * uy - (yj - yp) * ux   # moment of this reaction

    R_vals = np.linalg.solve(A, b)

    # Pack reactions into {jid: [Rx, Ry]}
    react = {jid: [0.0, 0.0] for jid in supports}
    for col, (jid, ux, uy) in enumerate(unknowns):
        react[jid][0] += R_vals[col] * ux
        react[jid][1] += R_vals[col] * uy

    return {jid: tuple(v) for jid, v in react.items()}


# ─────────────────────────────────────────────────────────────────────────────
#  SOLVER — METHOD OF JOINTS
# ─────────────────────────────────────────────────────────────────────────────

def method_of_joints(joints, members, supports, loads, reactions):
    n_mem         = len(members)
    joint_members = {jid: [] for jid in joints}
    for m_idx, (s, e) in enumerate(members):
        joint_members[s].append(m_idx)
        joint_members[e].append(m_idx)

    forces    = {}
    solve_log = []

    def ext_force(jid):
        fx, fy = loads.get(jid, (0.0, 0.0))
        if jid in reactions:
            rx, ry = reactions[jid]; fx += rx; fy += ry
        return fx, fy

    def unit_away(jid, m_idx):
        s, e = members[m_idx]
        other = e if s == jid else s
        xj, yj = joints[jid]; xo, yo = joints[other]
        L = np.hypot(xo - xj, yo - yj)
        if L < 1e-12:
            raise RuntimeError(f"Zero-length member between joints {s} and {e}.")
        return (xo - xj) / L, (yo - yj) / L

    def known_sum(jid):
        fx_k, fy_k = ext_force(jid)
        for m_idx in joint_members[jid]:
            if m_idx in forces:
                ux, uy = unit_away(jid, m_idx)
                fx_k += forces[m_idx] * ux
                fy_k += forces[m_idx] * uy
        return fx_k, fy_k

    def pick_next():
        best, best_n = None, 999
        for jid in joints:
            n_unk = sum(1 for m in joint_members[jid] if m not in forces)
            has_ext = jid in loads or jid in reactions
            priority = n_unk - (0.5 if has_ext else 0)
            if 0 < n_unk <= 2 and priority < best_n:
                best, best_n = jid, priority
        return best

    for _ in range(n_mem * 10):
        if len(forces) == n_mem:
            break
        jid = pick_next()
        if jid is None:
            break
        unk_ms = [m for m in joint_members[jid] if m not in forces]
        if len(unk_ms) > 2:
            continue

        fx_k, fy_k = known_sum(jid)

        if len(unk_ms) == 0:
            solve_log.append({"type": "verify", "joint": jid,
                               "residual_fx": fx_k, "residual_fy": fy_k})
            continue

        if len(unk_ms) == 1:
            m_idx  = unk_ms[0]
            ux, uy = unit_away(jid, m_idx)
            f = (-fx_k / ux if abs(ux) >= abs(uy) and abs(ux) > 1e-12
                 else -fy_k / uy if abs(uy) > 1e-12 else 0.0)
            forces[m_idx] = f
            solve_log.append({"type": "1-unk", "joint": jid, "solved": {m_idx: f}})

        else:
            m0, m1     = unk_ms
            ux0, uy0   = unit_away(jid, m0)
            ux1, uy1   = unit_away(jid, m1)
            A = np.array([[ux0, ux1], [uy0, uy1]])
            b_vec = np.array([-fx_k, -fy_k])
            det = A[0, 0] * A[1, 1] - A[0, 1] * A[1, 0]
            if abs(det) < 1e-10:
                continue
            sol = np.linalg.solve(A, b_vec)
            forces[m0], forces[m1] = sol[0], sol[1]
            solve_log.append({"type": "2-unk", "joint": jid,
                               "solved": {m0: sol[0], m1: sol[1]}})

    if len(forces) < n_mem:
        unsolved = [i for i in range(n_mem) if i not in forces]
        raise RuntimeError(
            f"Could not solve members {unsolved}. "
            "Check truss is stable and statically determinate.")

    return np.array([forces[i] for i in range(n_mem)]), solve_log


# ─────────────────────────────────────────────────────────────────────────────
#  VISUALISATION
# ─────────────────────────────────────────────────────────────────────────────

def fmt(val):
    a = abs(val)
    if a >= 1e6: return f"{val/1e6:.3f} MN"
    if a >= 1e3: return f"{val/1e3:.3f} kN"
    return f"{val:.2f} N"

def fmt_abs(val):
    a = abs(val)
    if a >= 1e6: return f"{a/1e6:.3f} MN"
    if a >= 1e3: return f"{a/1e3:.3f} kN"
    return f"{a:.2f} N"


def draw_truss(joints, members, labels, supports, loads, reactions, forces, solve_log):
    xs     = [v[0] for v in joints.values()]
    ys     = [v[1] for v in joints.values()]
    span_x = max(xs) - min(xs) or 1
    span_y = max(ys) - min(ys) or 1
    SZ     = span_x * 0.032

    fig, ax = plt.subplots(figsize=(17, 7.5))
    fig.patch.set_facecolor("#07101f")
    ax.set_facecolor("#07101f")
    ax.grid(True, color="#0e1c30", linewidth=0.4, zorder=0)
    for sp in ax.spines.values():
        sp.set_color("#1a3050")
    ax.tick_params(colors="#3a6080", labelsize=8)
    ax.set_xlabel("x  (m)", fontsize=9, color="#4a80a0")
    ax.set_ylabel("y  (m)", fontsize=9, color="#4a80a0")

    max_abs = max(abs(f) for f in forces) if len(forces) else 1.0
    t_cmap  = plt.cm.Blues
    c_cmap  = plt.cm.Reds

    # ── Members ──────────────────────────────────────────────────────────────
    for idx, (s, e) in enumerate(members):
        x1, y1 = joints[s]; x2, y2 = joints[e]
        f      = forces[idx]
        ratio  = abs(f) / max_abs
        lw     = 1.5 + ratio * 6.5
        color  = (t_cmap(0.35 + 0.55 * ratio) if f >= 0
                  else c_cmap(0.35 + 0.55 * ratio))
        ax.plot([x1, x2], [y1, y2], color=color, linewidth=lw,
                solid_capstyle="round", zorder=2)
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        dx, dy = x2 - x1, y2 - y1
        L      = np.hypot(dx, dy)
        ox, oy = -dy / L * SZ * 0.85, dx / L * SZ * 0.85
        nat    = "T" if f >= 0 else "C"
        tcol   = "#80d8ff" if f >= 0 else "#ff8080"
        ax.text(mx + ox, my + oy,
                f"{fmt_abs(f)}\n({nat})",
                ha="center", va="center", fontsize=7,
                color=tcol, fontfamily="monospace",
                bbox=dict(boxstyle="round,pad=0.22", fc="#020810",
                          ec=tcol, lw=0.6, alpha=0.9), zorder=6)

    # ── Joints ───────────────────────────────────────────────────────────────
    order_map  = {step["joint"]: rank for rank, step in enumerate(solve_log)}
    order_cmap = plt.cm.plasma

    for jid, (x, y) in joints.items():
        rank = order_map.get(jid, -1)
        jcol = (order_cmap(0.12 + 0.72 * rank / max(len(solve_log) - 1, 1))
                if rank >= 0 else "#3bb8ff")
        ax.plot(x, y, "o", markersize=11, color="#060e1e",
                markeredgecolor=jcol, markeredgewidth=2.3, zorder=7)
        ax.plot(x, y, ".", markersize=4.5, color=jcol, zorder=8)
        lbl   = labels.get(jid, str(jid))
        badge = f"({rank + 1})" if rank >= 0 else ""
        ax.text(x, y + SZ * 0.62, f"{lbl}{badge}",
                ha="center", va="bottom", fontsize=8.5,
                fontweight="bold", color=jcol,
                fontfamily="monospace", zorder=9)

    # ── Supports ─────────────────────────────────────────────────────────────
    for jid, sup in supports.items():
        x, y  = joints[jid]
        angle = sup.get("angle", 0.0)          # surface angle in degrees
        θ     = np.radians(angle)

        # Normal direction (perpendicular to surface, pointing away from truss)
        nx, ny = -np.sin(θ), np.cos(θ)         # unit normal

        # Triangle tip is at the joint; base is offset in normal direction
        base_x = x + nx * 2 * SZ
        base_y = y + ny * 2 * SZ
        # Tangent direction (along surface)
        tx, ty = np.cos(θ), np.sin(θ)

        tri = plt.Polygon(
            [[x,            y],
             [base_x - tx * SZ, base_y - ty * SZ],
             [base_x + tx * SZ, base_y + ty * SZ]],
            closed=True, fill=False,
            edgecolor="#f5c842", lw=1.8, zorder=10)
        ax.add_patch(tri)

        if sup["type"] == "pin":
            # Hatching line at base
            for k in range(6):
                bx = base_x + tx * (-SZ * 1.3 + k * SZ * 0.52)
                by = base_y + ty * (-SZ * 1.3 + k * SZ * 0.52)
                ax.plot([bx, bx - nx * SZ * 0.55 - tx * SZ * 0.35],
                        [by, by - ny * SZ * 0.55 - ty * SZ * 0.35],
                        color="#f5c842", lw=1, zorder=10)
            # Base line
            ax.plot([base_x - tx * SZ * 1.3, base_x + tx * SZ * 1.3],
                    [base_y - ty * SZ * 1.3, base_y + ty * SZ * 1.3],
                    color="#f5c842", lw=1.5, zorder=10)
        else:
            # Roller circles
            for sign in (-0.6, 0.6):
                cx_ = base_x + tx * sign * SZ
                cy_ = base_y + ty * sign * SZ
                circ = plt.Circle(
                    (cx_ + nx * SZ * 0.3, cy_ + ny * SZ * 0.3),
                    SZ * 0.27,
                    fill=False, edgecolor="#f5c842", lw=1.5, zorder=10)
                ax.add_patch(circ)
            ax.plot([base_x - tx * SZ * 1.3, base_x + tx * SZ * 1.3],
                    [base_y - ty * SZ * 1.3, base_y + ty * SZ * 1.3],
                    color="#f5c842", lw=1.5, zorder=10)

    # ── Applied loads ─────────────────────────────────────────────────────────
    if loads:
        max_load  = max(np.hypot(fx, fy) for fx, fy in loads.values()) or 1
        arr_scale = span_x * 0.09 / max_load
        for jid, (fx, fy) in loads.items():
            if abs(fx) + abs(fy) < 1e-6:
                continue
            x, y = joints[jid]
            mag  = np.hypot(fx, fy)
            ux, uy = fx / mag, fy / mag
            al   = mag * arr_scale
            ax.annotate("", xy=(x, y), xytext=(x - ux * al, y - uy * al),
                        arrowprops=dict(arrowstyle="-|>", color="#ff9900",
                                        lw=2.2, mutation_scale=15), zorder=11)
            ax.text(x - ux * al * 1.18, y - uy * al * 1.18,
                    fmt_abs(mag),
                    ha="center", va="center", fontsize=7.5,
                    color="#ffcc50", fontfamily="monospace",
                    bbox=dict(boxstyle="round,pad=0.2", fc="#0a0800",
                              ec="#604010", lw=0.5, alpha=0.9), zorder=12)

    # ── Reactions ────────────────────────────────────────────────────────────
    for jid, (rx_val, ry_val) in reactions.items():
        x, y = joints[jid]
        for val, (ux2, uy2) in [(rx_val, (1, 0)), (ry_val, (0, 1))]:
            if abs(val) < 1e-3:
                continue
            sign = np.sign(val); al = span_x * 0.09
            ax.annotate("",
                xy=(x + ux2 * sign * SZ * 1.2, y + uy2 * sign * SZ * 1.2),
                xytext=(x + ux2 * sign * (SZ * 1.2 + al),
                        y + uy2 * sign * (SZ * 1.2 + al)),
                arrowprops=dict(arrowstyle="-|>", color="#40e090",
                                lw=2, mutation_scale=13), zorder=11)
        parts = []
        if abs(rx_val) > 1: parts.append(f"Rx = {fmt(rx_val)}")
        if abs(ry_val) > 1: parts.append(f"Ry = {fmt(ry_val)}")
        if parts:
            ax.text(x + SZ * 4.5, y - SZ * 3.5, "\n".join(parts),
                    ha="left", va="top", fontsize=7.5,
                    color="#40e090", fontfamily="monospace",
                    bbox=dict(boxstyle="round,pad=0.28", fc="#030d08",
                              ec="#1a4030", lw=0.6, alpha=0.9), zorder=12)

    # ── Legend ────────────────────────────────────────────────────────────────
    legend_items = [
        mpatches.Patch(color=t_cmap(0.7),  label="Tension  (+)"),
        mpatches.Patch(color=c_cmap(0.7),  label="Compression  (−)"),
        mpatches.Patch(color="#f5c842",    label="Support"),
        mpatches.Patch(color="#ff9900",    label="Applied Load"),
        mpatches.Patch(color="#40e090",    label="Reaction"),
        mpatches.Patch(color="#cc88ff",    label="Joint solve order  ①②③…"),
    ]
    leg = ax.legend(handles=legend_items, loc="upper right",
                    framealpha=0.92, facecolor="#040c18",
                    edgecolor="#1a3050", labelcolor="white",
                    fontsize=8.5, title="Legend", title_fontsize=9)
    leg.get_title().set_color("#7ab8e0")

    ax.set_title(
        "2D Truss Analysis  —  Method of Joints"
        "    (ΣFx = 0,  ΣFy = 0  at every joint)",
        fontsize=13, color="#3bb8ff", pad=12,
        fontfamily="monospace", fontweight="bold")

    ax.set_aspect("equal", adjustable="datalim")
    pad = span_x * 0.22
    ax.set_xlim(min(xs) - pad, max(xs) + pad)
    ax.set_ylim(min(ys) - span_y * 0.9, max(ys) + span_y * 0.6)
    plt.tight_layout()
    return fig


# ─────────────────────────────────────────────────────────────────────────────
#  PRINTED REPORT
# ─────────────────────────────────────────────────────────────────────────────

def print_report(joints, members, labels, loads, reactions, forces, solve_log):
    W = 68
    print("\n" + "═" * W)
    print("  2D TRUSS  —  METHOD OF JOINTS".center(W))
    print("═" * W)

    # Reactions
    print("\n  REACTIONS")
    print("  " + "─" * 50)
    for jid, (rx, ry) in reactions.items():
        lbl = labels.get(jid, jid)
        print(f"    Joint {lbl}:  Rx = {fmt(rx):>12},  Ry = {fmt(ry):>12}")

    # Member forces
    print(f"\n{'═' * W}")
    print("  RESULTS — MEMBER FORCES")
    print(f"{'─' * W}")
    print(f"  {'#':>3}  {'Member':^10}  {'L (m)':>8}  {'Force':>14}  {'Nature':^13}")
    print(f"{'─' * W}")
    for idx, (s, e) in enumerate(members):
        xs_, ys_ = joints[s]; xe, ye = joints[e]
        L   = np.hypot(xe - xs_, ye - ys_)
        f   = forces[idx]
        ml  = f"{labels.get(s, s)}–{labels.get(e, e)}"
        nat = "TENSION" if f >= 0 else "COMPRESSION"
        print(f"  {idx:>3}  {ml:^10}  {L:>8.3f}  {fmt(f):>14}  {nat:^13}")
    print("═" * W + "\n")


# ─────────────────────────────────────────────────────────────────────────────
#  QUICK-LOAD PRESETS  (optional shortcut)
# ─────────────────────────────────────────────────────────────────────────────

def load_preset():
    """Return the same Pratt truss shown in the reference image."""
    joints = {
        0: (0.0, 0.0), 1: (2.0, 0.0), 2: (4.0, 0.0),
        3: (6.0, 0.0), 4: (8.0, 0.0),
        5: (1.0, 2.0), 6: (3.0, 2.0), 7: (5.0, 2.0), 8: (7.0, 2.0),
    }
    labels = {0:"A",1:"B",2:"C",3:"D",4:"E",5:"F",6:"G",7:"H",8:"I"}
    members = [
        (0,1),(1,2),(2,3),(3,4),
        (5,6),(6,7),(7,8),
        (0,5),(1,5),(1,6),(2,6),(2,7),(3,7),(3,8),(4,8),
    ]
    supports = {
        0: {"type": "pin",    "angle": 0.0},
        4: {"type": "roller", "angle": 0.0},
    }
    loads = {1: (0.0, -50e3), 2: (0.0, -80e3), 3: (0.0, -50e3)}
    return joints, labels, members, supports, loads


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║       2D TRUSS ANALYZER — Interactive Input Edition          ║
║       Method of Joints  (ΣFx=0, ΣFy=0 at every joint)       ║
╚══════════════════════════════════════════════════════════════╝
""")
    use_preset = yn("Load the built-in example Pratt truss? (say 'n' to enter your own)", "y")

    if use_preset:
        joints, labels, members, supports, loads = load_preset()
        print("\n  ✓  Preset truss loaded.")
    else:
        joints,  labels  = collect_joints()
        members          = collect_members(joints, labels)
        supports         = collect_supports(joints, labels)
        loads            = collect_loads(joints, labels)

    # ── Solve ─────────────────────────────────────────────────────────────
    print("\n  Computing reactions …")
    try:
        reactions = compute_reactions(joints, members, supports, loads)
    except Exception as e:
        print(f"\n  ✗  Reaction solver failed: {e}")
        return

    print("  Solving member forces via method of joints …")
    try:
        forces, solve_log = method_of_joints(
            joints, members, supports, loads, reactions)
    except Exception as e:
        print(f"\n  ✗  Member-force solver failed: {e}")
        return

    print("  ✓  Solution converged.\n")

    # ── Report ────────────────────────────────────────────────────────────
    print_report(joints, members, labels, loads, reactions, forces, solve_log)

    # ── Draw ──────────────────────────────────────────────────────────────
    print("  Generating figure …")
    fig = draw_truss(joints, members, labels, supports, loads,
                     reactions, forces, solve_log)

    out = "truss_analysis_output.png"
    fig.savefig(out, dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    print(f"  ✓  Figure saved → {out}\n")
    plt.show()


if __name__ == "__main__":
    main()
