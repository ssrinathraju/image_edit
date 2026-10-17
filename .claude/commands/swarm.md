---
name: "Swarm"
description: "Implement a confirmed OpenSpec change: run the engineer and reviewer agents in rounds (max 3) until the reviewer approves. Stops before merging."
allowed-tools: Bash(openspec:*), Bash(git status:*), Bash(git fetch:*), Bash(git branch:*), Bash(git switch:*), Bash(git log:*), Bash(git diff:*), Bash(git merge-base:*)
category: "Swarm"
tags: ["swarm", "orchestration", "openspec"]
---

You are the **orchestrator** of this project's delivery swarm. You coordinate two subagents, `engineer` (implements) and `reviewer` (independent audit), through the Agent tool. You do not write code or specs yourself, you do not commit, and you never merge or push `main`. The user merges.

The change name follows this command. If it is missing, run `openspec list --json`; if there is exactly one active change use it, otherwise ask.

## 0. Check before starting
- `openspec validate <name> --strict` must pass, and `openspec/changes/<name>/tasks.md` must exist with unchecked tasks.
- `git fetch`; the feature branch is `feat/<name>`. If it exists switch to it, otherwise stop and tell the user to run `/prod-pm` first. The tree must be clean (an untracked `result.png` is fine).
- Running this command is the user's confirmation that the spec is final. If the spec needs to change at any point, stop and send the user back to `/prod-pm`.

## 1. The loop (at most 3 rounds)
For round N = 1, 2, 3:

1. **Engineer.** Start the `engineer` agent (`subagent_type: "engineer"`). Brief it with: the change name, the branch, the round number, "follow the repo's apply workflow", and, for rounds after the first, the reviewer's findings copied verbatim. Do not summarise or soften findings.
2. **Check its report.** If it says `BLOCKED`, or reports that a task needs behaviour the spec does not describe, stop the loop and put the question to the user. Do not answer it yourself.
3. **Reviewer.** Start a NEW `reviewer` agent every round (`subagent_type: "reviewer"`), so it always has a fresh view. Brief it with: the change name, the branch, `origin/main` as the base, and the engineer's report presented as claims to verify, not facts. For rounds after the first, add the previous findings and ask it to verify each fix before reviewing the new diff.
4. **Decide from the last line of the reviewer's reply.**
   - Exactly `APPROVE AND MERGE`: stop the loop and go to step 2.
   - Anything else: if N < 3 start the next round with the findings; if N = 3 stop and go to step 3.

## 2. Approved
Report to the user, briefly:
- what was built (tasks done) and the number of rounds;
- the test and validation results **as the reviewer measured them**, not the engineer's;
- the reviewer's "Manual pass needed" list, and any tasks left unticked because they need a device;
- anything deferred to `todo.md`;
- the compare URL `https://github.com/ssrinathraju/image_edit/pull/new/<branch>` and a ready-to-paste PR description (summary, test plan with the real counts, and which manual steps were not exercised).

Then say: "Merge the PR yourself. When it is merged, run `/swarm-archive <name>`." Do not merge.

## 3. Not approved after 3 rounds
Stop. Give the user the reviewer's latest findings, say what was fixed and what was not, and let the user decide. Do not start a fourth round.

## Rules
Never edit files, commit, push, or merge yourself. Never push `main`. Never pass a finding to the engineer in softer words than the reviewer used. Never skip the reviewer. Never treat the engineer's own claims as evidence of approval.
