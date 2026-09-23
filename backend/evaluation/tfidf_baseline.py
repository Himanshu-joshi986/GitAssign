"""
TF-IDF text-only baseline recommender — Experiment A.
No file/component/recency/workload signals. Simplest possible matcher.
"""
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from db.init_db import get_conn

def build_baseline(repo: str, cutoff_date: str = None):
    """
    Returns (vectorizer, dev_matrix, dev_names) fitted on all developer corpora.
    cutoff_date: only use data before this date.
    """
    conn = get_conn()

    date_filter = " AND i.closed_at < ?" if cutoff_date else ""
    params = [repo]
    if cutoff_date:
        params.append(cutoff_date)

    rows = conn.execute(f"""
        SELECT l.resolver,
               GROUP_CONCAT(i.title || ' ' || COALESCE(i.body, ''), ' ') AS corpus
        FROM issues i
        JOIN issue_pr_links l ON l.repo=i.repo AND l.issue_num=i.number
        WHERE i.repo=? AND i.state='closed' AND l.resolver IS NOT NULL
        {date_filter}
        GROUP BY l.resolver
        HAVING COUNT(*) >= 5
    """, params).fetchall()
    conn.close()

    if not rows:
        return None, None, []

    dev_names = [r["resolver"] for r in rows]
    corpora   = [r["corpus"] or "" for r in rows]

    vec = TfidfVectorizer(max_features=8000, stop_words="english",
                          sublinear_tf=True, min_df=2)
    dev_matrix = vec.fit_transform(corpora)

    return vec, dev_matrix, dev_names

def recommend_baseline(issue_text: str, vec, dev_matrix, dev_names: list, top_k: int = 5) -> list:
    """
    Returns ranked [(developer, score), ...].
    """
    if vec is None or not dev_names:
        return []
    issue_vec = vec.transform([issue_text])
    scores = cosine_similarity(issue_vec, dev_matrix).flatten()
    ranked_idx = np.argsort(scores)[::-1][:top_k]
    return [(dev_names[i], float(scores[i])) for i in ranked_idx]

if __name__ == "__main__":
    import sys
    repo = sys.argv[1] if len(sys.argv) > 1 else "eclipse/jdt"
    print(f"Building TF-IDF baseline for {repo}...")
    vec, matrix, names = build_baseline(repo)
    if not names:
        print("No developer data found. Load dataset first.")
        sys.exit(1)
    print(f"  {len(names)} developers in model")
    test_issue = "NullPointerException when opening connection pool under high load"
    results = recommend_baseline(test_issue, vec, matrix, names)
    print(f"\nTest query: '{test_issue}'")
    print("Top 5 recommendations:")
    for dev, score in results:
        print(f"  {dev}: {score:.4f}")
