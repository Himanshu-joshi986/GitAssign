"""
Load Eclipse JDT or Mozilla bugs from logpai/bughub CSV into GitAssign DB.
Download: https://github.com/logpai/bughub

Usage:
    python scripts/load_bughub.py data/eclipse_jdt_clean.csv eclipse/jdt
    python scripts/load_bughub.py data/mozilla_firefox_clean.csv mozilla/firefox

If the CSV has no fixer/assignee column (e.g. some bughub versions),
developers are SYNTHESIZED from the Component column — each component
gets a dedicated "dev_<component>" pseudo-developer. This ensures the
profiles → scoring → recommendation pipeline has ground truth to work
with, and component expertise signals work naturally.
"""
import sys, os, json, hashlib, re
from datetime import datetime, timezone
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db.init_db import get_conn, init_db

MIN_BUGS_PER_DEV = 5  # Lowered from 10 — component pseudo-devs cluster tightly


def _normalise_date(s: str) -> str:
    """Normalise common bugreport date formats to ISO 8601 (parsable by fromisoformat)."""
    if not s:
        return ""
    s = str(s).strip()
    # Already ISO
    for candidate in (s, s.replace("Z", "+00:00")):
        try:
            datetime.fromisoformat(candidate)
            return candidate
        except Exception:
            pass
    # YYYY-MM-DD HH:MM:SS ±HHMM (bughub format)
    m = re.match(r"^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})\s*([+-]\d{2})(\d{2})$", s)
    if m:
        d, t, sh, sm = m.groups()
        return f"{d}T{t}{sh}:{sm}"
    # YYYY-MM-DD HH:MM:SS ±HH:MM
    m2 = re.match(r"^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})\s*([+-]\d{2}):(\d{2})$", s)
    if m2:
        d, t, sh, sm = m2.groups()
        return f"{d}T{t}{sh}:{sm}"
    # Date-only
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s + "T00:00:00+00:00"
    # Fallback formats
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc).isoformat()
        except Exception:
            continue
    return s  # Return as-is; recency_score handles unknowns gracefully


def _derive_fixer(row: pd.Series, col_map: dict, dev_initial_map: dict) -> str:
    """
    Determine a fixer/resolver for one row.
    Priority:
      1. Explicit fixed_by column if present & non-empty
      2. Synthesize from Component → "dev_<component>" (best for JDT CSV w/o names)
    """
    # 1) Real fixer column if exists
    if "fixed_by" in col_map:
        val = str(row.get("fixed_by", "") or "").strip()
        if val and val.lower() not in ("nan", "none", ""):
            return val

    # 2) Fallback: derive from Component
    comp = str(row.get("component", "") or "").strip()
    if comp and comp.lower() not in ("nan", "none", ""):
        return f"dev_{comp.lower().replace(' ', '_')}"

    # 3) Last resort: author from description initials (e.g. "JGS (date); ...")
    desc = str(row.get("long_desc", "") or row.get("body", "") or "")
    if "(" in desc and ";" in desc:
        maybe_initials = desc.split("(", 1)[0].strip()
        if 2 <= len(maybe_initials) <= 6 and maybe_initials.isalpha():
            cache_key = maybe_initials.lower()
            if cache_key not in dev_initial_map:
                dev_initial_map[cache_key] = f"dev_{maybe_initials.lower()}"
            return dev_initial_map[cache_key]

    return ""


def load_bughub(csv_path: str, repo: str = "eclipse/jdt"):
    init_db()
    print(f"[bughub] loading {csv_path} → repo={repo}")
    df = pd.read_csv(csv_path, encoding="latin-1", on_bad_lines="skip")
    print(f"  raw rows: {len(df)}, columns: {list(df.columns)}")

    col_map = {}
    cols_lower = {c.lower(): c for c in df.columns}
    for target, candidates in {
        "bug_id":     ["bug_id", "id", "issue_id"],
        "short_desc": ["short_desc", "summary", "title", "short_description"],
        "long_desc":  ["long_desc", "description", "body", "long_description"],
        "status":     ["status", "state", "resolution"],
        "fixed_by":   ["fixed_by", "resolver", "assignee", "who"],
        "created_at": ["creation_ts", "created_at", "open_date", "date", "created_time"],
        "closed_at":  ["delta_ts", "closed_at", "close_date", "last_change_time", "resolved_time"],
        "component":  ["component", "product", "area"],
        "priority":   ["priority", "severity", "bug_severity"],
    }.items():
        for c in candidates:
            if c in cols_lower:
                col_map[target] = cols_lower[c]
                break

    print(f"  column map: {col_map}")
    has_real_fixer = "fixed_by" in col_map
    if not has_real_fixer:
        print(f"  [bughub] NOTE: No fixer/resolver column found. Developers will be SYNTHESIZED from Component column.")

    for target, src in col_map.items():
        if target not in df.columns:
            df[target] = df[src]

    # Keep only resolved ones — but allow even without a named fixer yet (we derive below)
    if "status" in df.columns:
        df["status"] = df["status"].astype(str)
        mask = df["status"].str.upper().fillna("").isin(["RESOLVED", "CLOSED", "FIXED", "VERIFIED"])
        df = df[mask]

    # Derive fixer for every row (real or synthesized)
    dev_initial_map: dict = {}
    df["fixed_by"] = df.apply(lambda r: _derive_fixer(r, col_map, dev_initial_map), axis=1)
    df = df[df["fixed_by"] != ""]

    # Filter to developers with enough bugs
    dev_counts = df["fixed_by"].value_counts()
    active_devs = dev_counts[dev_counts >= MIN_BUGS_PER_DEV].index
    df = df[df["fixed_by"].isin(active_devs)]

    print(f"  after filter: {len(df)} bugs, {df['fixed_by'].nunique()} developers")
    if not has_real_fixer:
        top = dev_counts.head(10)
        print(f"  top 10 component pseudo-devs: {dict(top)}")

    conn = get_conn()
    bugs_inserted = 0
    links_inserted = 0

    for _, row in df.iterrows():
        try:
            bug_id_raw = row.get("bug_id", 0)
            bug_id = int(float(bug_id_raw))
        except (ValueError, TypeError):
            bug_id = 0
        if bug_id <= 0:
            bugs_inserted += 1
            bug_id = 1000000 + bugs_inserted
        title  = str(row.get("short_desc", "") or "")[:500]
        body   = (str(row.get("long_desc", "") or ""))[:2000] if "long_desc" in row else ""
        fixed  = str(row.get("fixed_by", "") or "").strip()
        comp_raw = str(row.get("component", "") or "").strip()
        comp   = "" if comp_raw.lower() in ("nan", "none") else comp_raw
        pri_raw = str(row.get("priority", "") or "").strip()
        pri    = "" if pri_raw.lower() in ("nan", "none") else pri_raw
        created_raw = str(row.get("created_at", "") or "").strip()
        created = "" if created_raw.lower() in ("nan", "none") else created_raw
        closed_raw = str(row.get("closed_at", "") or "").strip()
        closed  = "" if closed_raw.lower() in ("nan", "none") else closed_raw

        labels_list = []
        if comp:
            labels_list.append(comp)
        if pri:
            labels_list.append(pri)
        labels = json.dumps(labels_list)

        # Normalise dates at load time for downstream recency calculation
        created = _normalise_date(created) if created else ""
        closed = _normalise_date(closed) if closed else ""

        try:
            conn.execute("""
                INSERT INTO issues (repo, number, title, body, labels, state, created_at, closed_at, author)
                VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(repo, number) DO NOTHING
            """, (repo, bug_id, title, body, labels, "closed", created, closed, fixed))
            bugs_inserted += 1
        except Exception:
            continue

        if fixed:
            conn.execute(
                "INSERT OR IGNORE INTO developers (username, display_name) VALUES (?,?)",
                (fixed, fixed)
            )
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO issue_pr_links (repo, issue_num, pr_num, link_type, resolver)
                    VALUES (?,?,?,?,?)
                """, (repo, bug_id, 0,
                      "bughub_ground_truth" if has_real_fixer else "bughub_component_synth",
                      fixed))
                links_inserted += 1
            except Exception:
                pass

    conn.commit()
    conn.close()
    print(f"[bughub] done: {bugs_inserted} bugs, {links_inserted} ground-truth links loaded")


def prepare_dataset(csv_path: str, out_path: str = None, repo: str = "eclipse/jdt"):
    """Download, filter, and show dataset stats."""
    df = pd.read_csv(csv_path, encoding="latin-1", on_bad_lines="skip")
    print(f"Raw rows: {len(df)}")
    print(f"Columns: {list(df.columns)}")

    fixer_col = next((c for c in df.columns if "fix" in c.lower() or "who" in c.lower() or "assign" in c.lower()), None)
    if fixer_col:
        dev_counts = df[fixer_col].value_counts()
        print(f"\nTop 10 developers (by {fixer_col}):")
        print(dev_counts.head(10).to_string())
        active = dev_counts[dev_counts >= MIN_BUGS_PER_DEV]
        print(f"\nDevelopers with >= {MIN_BUGS_PER_DEV} bugs: {len(active)}")
        print(f"Total bugs after dev filter: {df[df[fixer_col].isin(active.index)].shape[0]}")
    else:
        print("\n[bughub] No fixer column in CSV — will synthesize devs from Component.")
        comp_col = next((c for c in df.columns if "comp" in c.lower() or "prod" in c.lower()), None)
        if comp_col:
            comp_counts = df[comp_col].value_counts()
            print(f"Top 10 components ({comp_col}):")
            print(comp_counts.head(10).to_string())


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python load_bughub.py <path_to_csv> [repo_name]")
        print("Example: python load_bughub.py data/eclipse.csv eclipse/jdt")
        sys.exit(1)
    csv_path = sys.argv[1]
    repo = sys.argv[2] if len(sys.argv) > 2 else "eclipse/jdt"
    load_bughub(csv_path, repo)
