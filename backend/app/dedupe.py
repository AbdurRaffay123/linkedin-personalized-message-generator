"""Merge duplicate prospects created before URL-keyed capture merging existed.

LinkedIn keeps About/Experience on /in/<slug> and posts on the activity feed, so
early captures of the same person landed as separate prospects with different
URLs (and sometimes a section-label name like "Activity"). This groups prospects
by canonical profile URL, merges each group into one (filling blank fields,
moving posts + analyses, keeping the best name), and deletes the emptied dupes.

Usage:
    python -m app.dedupe            # dry run — report what would merge
    python -m app.dedupe --apply    # perform the merge
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict

from app.db.base import SessionLocal
from app.db.models import Prospect


def canonical(url: str | None) -> str | None:
    if not url:
        return None
    m = re.search(r"/in/([^/?#]+)", url)
    return f"https://www.linkedin.com/in/{m.group(1)}/" if m else url


def _has_full_name(name: str | None) -> bool:
    return bool(name and " " in name.strip())


def main(argv: list[str]) -> int:
    apply = "--apply" in argv
    db = SessionLocal()
    try:
        prospects = db.query(Prospect).all()
        groups: dict[tuple[int, str], list[Prospect]] = defaultdict(list)
        for p in prospects:
            canon = canonical(p.linkedin_url)
            if canon is None:
                continue  # nothing to key on; leave it alone
            groups[(p.user_id, canon)].append(p)

        merged = 0
        for (_user_id, canon), plist in groups.items():
            # Normalize the URL on every prospect so future captures merge.
            for p in plist:
                p.linkedin_url = canon
            if len(plist) < 2:
                continue

            # Primary = a real-named one if present, else the earliest capture.
            plist.sort(key=lambda p: (0 if _has_full_name(p.full_name) else 1, p.captured_at))
            primary, dups = plist[0], plist[1:]
            print(f"\n{canon}")
            print(f"  keep  #{primary.id} '{primary.full_name}' "
                  f"(posts={len(primary.posts)})")
            for dup in dups:
                print(f"  merge #{dup.id} '{dup.full_name}' "
                      f"(posts={len(dup.posts)}, analyses={len(dup.analyses)})")
                # Fill blank scalar fields from the duplicate.
                primary.about = primary.about or dup.about
                primary.experience = primary.experience or dup.experience
                primary.education = primary.education or dup.education
                primary.skills = primary.skills or dup.skills
                primary.headline = primary.headline or dup.headline
                if not primary.company_id:
                    primary.company_id = dup.company_id
                # Upgrade a placeholder name to a real one.
                if _has_full_name(dup.full_name) and not _has_full_name(primary.full_name):
                    primary.full_name = dup.full_name
                # Move new posts (dedupe by content) and all analyses.
                seen = {x.content for x in primary.posts}
                for post in list(dup.posts):
                    if post.content not in seen:
                        dup.posts.remove(post)
                        primary.posts.append(post)
                        seen.add(post.content)
                for a in list(dup.analyses):
                    dup.analyses.remove(a)
                    primary.analyses.append(a)
                if apply:
                    db.delete(dup)
                merged += 1

        if apply:
            db.commit()
            print(f"\nMerged {merged} duplicate prospect(s).")
        else:
            db.rollback()
            print(f"\nDRY RUN — would merge {merged} duplicate(s). "
                  f"Re-run with --apply to perform it.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
