# Minimal add-on

The smallest valid MRI Agent Bench add-on: a manifest (addon.json), one skill in the Agent Skills format and an optional
AGENTS.md pointer. This README is not part of the installed add-on.

    mrab addon validate examples/addons/minimal
    mrab pair <instance> --agent codex --model <model> --addon examples/addons/minimal --run 1

See docs/EVALUATE-YOUR-SKILLS.md.
