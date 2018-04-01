# aws-docs-diff

When sync is run, we use a uniform timestamp to threshold everything.

- First, get all docs repos.
- For each repo:
  - If the repo is new, clone it, write an empty file to the diffs repo and skip to the next repo. Otherwise:
  - Fetch commits (only need master).
    - This moves FETCH_HEAD, but not HEAD (HEAD stays where it was last)
  - Find the newest commit in FETCH_HEAD's history *before* the timestamp (could be FETCH_HEAD, or a parent).
  - If this is different from HEAD, get the diff between HEAD and that commit. Otherwise, diff is empty string.
  - Write diff to diffs repo.
- Commit the diffs repo. Commit message and commit time are the timestamp.
- For each repo, move HEAD to the updated commit (latest before the timestamp).

TODO:
- How do we store more state about the diff in the diffs repo? We are relying on HEAD not getting moved in the docs repo in between syncs. Ideally the diffs repo contains all the information necessary to constitute the state for each docs repo
- Docs repo is current `git init`'d if it doesn't exist. It should have an origin.
- Should the code and diffs live in the same repo on GitHub?
