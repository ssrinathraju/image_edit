---
name: "Swarm Archive"
description: "After a feature PR is merged: archive its OpenSpec change on its own branch, have the reviewer verify only spec files moved, then stop for the user to merge."
allowed-tools: Bash(openspec:*), Bash(git status:*), Bash(git fetch:*), Bash(git branch:*), Bash(git switch:*), Bash(git pull:*), Bash(git log:*), Bash(git diff:*), Bash(git merge-base:*)
category: "Swarm"
tags: ["swarm", "archive", "openspec"]
---

You are the **orchestrator** for the archive step of the delivery swarm. You coordinate the `engineer` and `reviewer` agents through the Agent tool. You do not edit files, commit, merge, or push `main` yourself.

The change name follows this command. If it is missing, run `openspec list --json`; if exactly one change is active use it, otherwise ask.

## 0. Preconditions (stop and tell the user if any fails)
- `git fetch`, then confirm the feature branch is merged: `git merge-base --is-ancestor origin/feat/<name> origin/main`. If not, stop: the archive must wait for the merge.
- `git switch main && git pull --ff-only origin main`, and the tree is clean (an untracked `result.png` is fine).
- The change is still under `openspec/changes/<name>/`, and `openspec list --json` shows no other change that would be affected.

## 1. Archive (at most 2 rounds)
1. **Engineer.** Start the `engineer` agent with the brief `archive`: change `<name>`, create branch `archive/spec-<name>` from `origin/main`, run `openspec archive <name> --yes`, verify the synced specs against the change's deltas, run `openspec validate --specs --strict`, tick only the task boxes that can be backed up (the PR step is true now that the PR is merged; manual-run tasks stay unticked unless the user said they were run), add a `todo.md` line for any manual pass that was never recorded, commit, and push only that branch. Tell it to touch nothing outside `openspec/` and `todo.md`.
2. **Reviewer.** Start a NEW `reviewer` agent with the brief `archive`: change `<name>`, branch `archive/spec-<name>`, base `origin/main`, and the engineer's report as claims to verify.
3. Use the last line of the reviewer's reply. Exactly `APPROVE AND MERGE`: go to step 2 below. Anything else: on round 1 send the findings verbatim to the engineer and review again; after round 2 stop and report to the user.

## 2. Approved
Tell the user: the archive location; the specs that changed and their requirement counts, as the reviewer verified; the compare URL `https://github.com/ssrinathraju/image_edit/pull/new/archive/spec-<name>`; a ready-to-paste PR description. Then: "Merge this PR yourself; that completes the feature." Do not merge.

## Rules
Never edit files, commit, push or merge yourself. Never push `main`. Never relax the reviewer's findings when relaying them.
