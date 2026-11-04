# MRI Agent Bench website

The canonical project website is <https://kewang0622.github.io/MRIAgentBench/>.
It is a static HTML/CSS/JavaScript site deployed by the repository’s Pages workflow.
No frontend package installation or build step is required.

Preview from the repository root:

```sh
python -m http.server 8767 --bind 127.0.0.1
# Open http://127.0.0.1:8767/site/
```

`data/` is generated from the public catalog and the frozen, disclosure-limited results
snapshot. Run `make build-site` to regenerate it and `make check-results` to check it.
Do not edit generated data or copy private Hard task material into the website.

The overview’s workflow and task visuals are original illustrative SVGs. They describe
inputs, selected required artifacts and verification; they are not measured runs or MRI
reconstructions. Task examples link to `SEQ-05`, `RECON-01` and `WRITE-02` in the canonical
public catalog. The aggregate study panel reads the same saved data and formatting
helpers as the full Results page. Keep the dated study distinct from community submissions.

When changing layout, check Overview, Tasks, Run and Results at desktop and phone widths;
exercise catalog search, domain filters, task anchors, expanded variants, result details
and copy buttons. Wide workflows, code blocks and result tables scroll within their own
containers. Links to a collapsed results section open it automatically.
