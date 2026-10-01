"""Generates stats.svg, languages.svg and activity.svg from REAL GitHub data.

Data source: GitHub GraphQL API, authenticated with the workflow's GITHUB_TOKEN.
Nothing is hardcoded or estimated. If the API call fails, the script exits with
an error and the workflow fails (no fake fallback).
"""
import datetime
import html
import json
import os
import sys
import urllib.request

LOGIN = "krupasawarkar630"
OUT = sys.argv[1] if len(sys.argv) > 1 else "dist-stats"

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    repositories(ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC, first: 100) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""

STYLE = """<style>
.bg{fill:#ffffff;stroke:#d0d7de}.t{fill:#1f2328;font:600 15px 'Segoe UI',Ubuntu,sans-serif}
.l{fill:#1f2328;font:13px 'Segoe UI',Ubuntu,sans-serif}.m{fill:#656d76;font:11px 'Segoe UI',Ubuntu,sans-serif}
.f{fill:#0969da}.s{stroke:#0969da;fill:none;stroke-width:2}.g{stroke:#d0d7de}.ar{fill:#0969da;fill-opacity:.15}
@media (prefers-color-scheme: dark){
.bg{fill:#0d1117;stroke:#30363d}.t{fill:#e6edf3}.l{fill:#e6edf3}.m{fill:#8b949e}
.f{fill:#58a6ff}.s{stroke:#58a6ff}.g{stroke:#30363d}.ar{fill:#58a6ff;fill-opacity:.18}}
</style>"""


def esc(s):
    return html.escape(str(s))


def fetch(token):
    body = json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "profile-stats"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data or not data.get("data", {}).get("user"):
        raise SystemExit(f"GitHub API error: {data.get('errors')}")
    return data["data"]["user"]


def frame(w, h, title, inner):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'role="img" aria-label="{esc(title)}"><title>{esc(title)}</title>{STYLE}'
            f'<rect class="bg" x=".5" y=".5" width="{w-1}" height="{h-1}" rx="8"/>'
            f'<text class="t" x="20" y="30">{esc(title)}</text>{inner}</svg>')


def days_list(user):
    cal = user["contributionsCollection"]["contributionCalendar"]
    return [d for w in cal["weeks"] for d in w["contributionDays"]]


def streaks(days):
    today = datetime.date.today().isoformat()
    days = [d for d in days if d["date"] <= today]
    longest = run = 0
    for d in days:
        run = run + 1 if d["contributionCount"] > 0 else 0
        longest = max(longest, run)
    cur = 0
    for i, d in enumerate(reversed(days)):
        if d["contributionCount"] > 0:
            cur += 1
        elif i == 0:  # today may not have a contribution yet
            continue
        else:
            break
    return cur, longest


def render_stats(user):
    cc = user["contributionsCollection"]
    stars = sum(n["stargazerCount"] for n in user["repositories"]["nodes"])
    cur, longest = streaks(days_list(user))
    rows = [
        ("Contributions (last year)", cc["contributionCalendar"]["totalContributions"]),
        ("Commits (last year)", cc["totalCommitContributions"]),
        ("Pull requests / Issues", f'{cc["totalPullRequestContributions"]} / {cc["totalIssueContributions"]}'),
        ("Public repos (non-fork) / Stars", f'{user["repositories"]["totalCount"]} / {stars}'),
        ("Followers", user["followers"]["totalCount"]),
        ("Current / longest streak (days)", f"{cur} / {longest}"),
    ]
    inner = ""
    for i, (k, v) in enumerate(rows):
        y = 58 + i * 24
        inner += f'<text class="l" x="20" y="{y}">{esc(k)}</text><text class="l" x="395" y="{y}" text-anchor="end" font-weight="600">{esc(v)}</text>'
    return frame(415, 205, "GitHub Stats (live from GitHub)", inner)


def render_languages(user):
    totals, colors = {}, {}
    for repo in user["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            n = e["node"]["name"]
            totals[n] = totals.get(n, 0) + e["size"]
            colors[n] = e["node"]["color"] or "#8b949e"
    total = sum(totals.values())
    top = sorted(totals.items(), key=lambda x: -x[1])[:6]
    if not total:
        return frame(415, 205, "Most Used Languages", '<text class="m" x="20" y="60">No language data found.</text>')
    inner, x = '<clipPath id="c"><rect x="20" y="44" width="375" height="10" rx="5"/></clipPath><g clip-path="url(#c)">', 20.0
    for n, b in top:
        w = 375 * b / total
        inner += f'<rect x="{x:.2f}" y="44" width="{w:.2f}" height="10" fill="{esc(colors[n])}"/>'
        x += w
    inner += "</g>"
    for i, (n, b) in enumerate(top):
        cx, cy = 20 + (i % 2) * 190, 82 + (i // 2) * 28
        inner += (f'<circle cx="{cx+5}" cy="{cy-4}" r="5" fill="{esc(colors[n])}"/>'
                  f'<text class="l" x="{cx+16}" y="{cy}">{esc(n)}</text>'
                  f'<text class="m" x="{cx+175}" y="{cy}" text-anchor="end">{100*b/total:.1f}%</text>')
    return frame(415, 205, "Most Used Languages (non-fork repos)", inner)


def render_activity(user, n=90):
    days = [d for d in days_list(user) if d["date"] <= datetime.date.today().isoformat()][-n:]
    counts = [d["contributionCount"] for d in days]
    peak = max(max(counts), 1)
    L, R, T, B = 40, 880, 50, 190
    step = (R - L) / max(len(counts) - 1, 1)
    pts = [(L + i * step, B - (c / peak) * (B - T)) for i, c in enumerate(counts)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    inner = ""
    for frac in (0, .5, 1):
        y = B - frac * (B - T)
        inner += (f'<line class="g" x1="{L}" x2="{R}" y1="{y:.1f}" y2="{y:.1f}"/>'
                  f'<text class="m" x="{L-6}" y="{y+4:.1f}" text-anchor="end">{round(peak*frac)}</text>')
    inner += f'<polygon class="ar" points="{L},{B} {line} {R},{B}"/><polyline class="s" points="{line}"/>'
    inner += (f'<text class="m" x="{L}" y="{B+18}">{esc(days[0]["date"])}</text>'
              f'<text class="m" x="{R}" y="{B+18}" text-anchor="end">{esc(days[-1]["date"])}</text>')
    total = sum(counts)
    return frame(900, 225, f"Contribution Activity - last {len(days)} days ({total} contributions)", inner)


def main():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN is not set")
    user = fetch(token)
    os.makedirs(OUT, exist_ok=True)
    for name, fn in (("stats.svg", render_stats), ("languages.svg", render_languages),
                     ("activity.svg", render_activity)):
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            f.write(fn(user))
        print("wrote", name)


if __name__ == "__main__":
    main()
