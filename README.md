# Skill Selector

Find the right skill when you have hundreds installed.

Agent hosts put every installed skill's name and description into the model's context. Past a few hundred skills that list gets cut: Claude Code drops descriptions once the listing budget is full, and Codex can drop descriptions entirely and leave skills out of the list. The model then picks skills from names alone, or never sees the right one.

Skill Selector keeps your skills where they are and adds one entry point that searches all of them:

- it indexes every `SKILL.md` it can find (Claude Code user and plugin skills, Codex user and plugin skills, `~/.agents/skills`, the Claude app sandbox), across hosts;
- on each prompt, a hook suggests up to three skills when the prompt clearly matches one;
- for prompts in other languages, where keyword matching cannot work, it tells the model to search with English keywords before doing anything else;
- the model loads only the skill it picked.

It is one Python file using only the standard library. It makes no network calls and changes nothing outside `~/.skill-selector/` unless you run `park`, `unpark` or `pack`.

## Install

**Claude Code**

```
/plugin marketplace add <repo>
/plugin install skill-selector@skill-selector
```

Start a new session afterwards; hooks load at session start.

**Codex**

```
codex plugin marketplace add <repo>
codex plugin add skill-selector@skill-selector
```

Codex runs plugin hooks only after you trust them. The next time you open Codex it shows **Hooks need review**: choose **Review hooks** and trust the two `skill-selector` hooks (session start and prompt submit). Until then the skill still works when you call it (`$skill-selector`), but nothing is suggested automatically.

`<repo>` is `buyuksahinbatu/skill-selector` (or the path of a local clone).

**Claude app** (claude.ai and Claude Desktop)

Run `python3 tools/build_release.py`, then upload `dist/skill-selector.plugin` under Customize > Plugins, or `dist/skill-selector.zip` under Customize > Skills. Hooks do not run in Claude app chat (they do in Cowork), so in chat the model uses the skill when its description fits or when you ask for it. See [Claude app library](#claude-app-library) to bundle the skills you use there.

**Requirements:** `python3` 3.8 or newer on `PATH`. Tested on macOS and Linux. On Windows the hooks need a `python3` command, and `park` is not supported.

## How it behaves

- **Session start:** rebuilds the index (time-boxed to 3 seconds) and, when at least 50 skills are installed, tells the model how to search them.
- **Each prompt:** suggests up to three skills only on a strong match, meaning words in the prompt that are rare among your skills. Ordinary words like *fix*, *test* or *page* never trigger it.
- **Non-English prompts:** when a prompt has no strong match and looks non-English, the hook asks the model to run a search with English keywords first, and lists any skills that match the few recognisable words (product names, for example).
- **Below 50 skills** the host's own list is complete, so the hooks stay silent.

Turn suggestions off with `SKILL_SELECTOR_HOOK=off`, or with `"hook_suggestions": false` in `~/.skill-selector/config.json`. Turn the non-English reminder off with `"hook_reminders": false`.

## Commands

The session-start hint prints the full script path. Inside a clone, the script is `skills/skill-selector/scripts/selector.py`.

```sh
python3 scripts/selector.py search 'reconcile supplier invoices' --top 3
python3 scripts/selector.py show <name>
python3 scripts/selector.py doctor
python3 scripts/selector.py index
```

- `search` ranks skills and prints each one's source and `SKILL.md` path. `--json` gives the same as JSON.
- `show` prints a skill's base directory and full instructions; `--source LABEL` picks among same-name copies.
- `doctor` reports how many skills and how much listing text each source contributes, duplicate names, and files it could not read.
- `index` rebuilds the index after you install or remove skills (it also rebuilds itself after 24 hours).

`~/.skill-selector/config.json` (optional):

```json
{"extra_roots": [], "exclude_sources": [], "hook_suggestions": true, "hook_reminders": true, "top": 3}
```

## Security and privacy

- **Local only.** No network access, no telemetry, no subprocesses. The selector reads files and prints text.
- **Skill text is untrusted.** Names, descriptions and paths come from third-party `SKILL.md` files and are shown to the model as data. A name that is not a plain identifier (letters, digits, `.`, `_`, `:`, `-`, at most 64 characters) is replaced by the folder name, or the skill is skipped. Control characters, bidirectional and zero-width characters, and anything that imitates the selector's own markers are removed. Descriptions are cut short and quoted.
- **Shell-safe command.** The search command given to the model quotes the script path with `shlex.quote` and puts the keywords in single quotes, so the shell never expands them.
- **Loading a skill means following it.** Like any installed skill, a skill the model loads can tell it what to do. Install skills only from sources you trust; the selector does not judge skill quality or safety.

## Shrinking the list (optional)

You do not need this to use the selector. If a host struggles with too many skills, you can move some out of its folders reversibly. They stay searchable.

```sh
python3 scripts/selector.py doctor
python3 scripts/selector.py park --source claude-user --keep code-review,debugging
python3 scripts/selector.py park --source claude-user --keep code-review,debugging --apply
python3 scripts/selector.py parked
python3 scripts/selector.py unpark --all
```

- Without `--apply`, `park` only prints what it would move.
- Eligible sources are `claude-user` (`~/.claude/skills`), `codex-user` (`~/.codex/skills`) and `agents-user` (`~/.agents/skills`, which several tools read). Project and plugin skills cannot be parked; disable a plugin in its host instead.
- A symlinked skill is parked by removing the link and recording its target; parking a folder also parks the links that point to it.
- Moves use rename only, so a skill is never left half-copied: parking is refused if `~/.skill-selector` is on another disk.
- `unpark` refuses to overwrite a path that exists again. Hidden folders such as `.archive` are never indexed or moved.

## Claude app library

Hooks do not run in Claude app chat. To make a set of skills available there through one upload, bundle them:

```sh
python3 scripts/selector.py pack code-review debugging --out dist
```

Upload `dist/skill-selector-pack.zip` under Customize > Skills, in place of `skill-selector.zip` (both are named `skill-selector`). The uploaded selector searches its bundled library. Use `name@source` for same-name skills. Each skill may include up to 5 MiB of files; `--force` lifts the limit.

## Uninstall

- Claude Code: `/plugin uninstall skill-selector@skill-selector`, then `/plugin marketplace remove skill-selector`.
- Codex: `codex plugin remove skill-selector@skill-selector`, then `codex plugin marketplace remove skill-selector`.
- Run `unpark --all` first if you parked anything, then delete `~/.skill-selector/`.

## Limits

- Matching is lexical (BM25 over names, descriptions and the start of each skill body). It does not understand synonyms; the model bridges that by choosing the search keywords.
- Suggestions are hints. The model decides whether a skill fits, and following a non-English reminder is up to the model too: it worked in most but not all of our test runs.
- Codex has a built-in skill search for its own skills. This plugin adds search across all hosts' skill folders and the prompt-time hints.

## Development

```sh
python3 -m unittest discover -s tests -v
python3 tools/build_release.py --out dist
```

Tests run against a temporary home directory and never touch your real skill folders.

## License

MIT
