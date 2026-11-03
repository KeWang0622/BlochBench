# RECON-02 · Learned versus classical quantitative reconstruction

- Task ID: RECON-02
- Legacy ID: v5-learnrecon

- Domain: Reconstruction
- Tier: Core (v1.0 candidate); review status: pending
- Time cap: 60 min
- Instances recorded: 4 (instances.json)
- Automated checks (13): deliverables_present, split_by_subject, public_recon_schema, public_data_consistency, public_learned_downstream, public_classical_downstream, reported_downstream_matches_recon, validation_comparison_reported, hidden_learned_runs, hidden_learned_downstream, hidden_classical_runs, hidden_classical_downstream, readme_validation_limitations

## Task (example instance)

~~~text
We need to decide whether a small learned reconstruction is worth adopting for accelerated multi-echo gradient-echo scans, and what matters to us is the quantitative output, R2* and the field offset (B0) in tissue regions, rather than how the images look. task.json describes the training and test data, the k-space and sampling conventions, the signal model, the exact downstream R2*/B0 region analysis, the comparison protocol and the file schemas.

Train a small reconstruction network on the CPU from the fully sampled training data, set up and tune a classical reconstruction, and compare the two, with zero filling as a baseline, on validation subjects held out by subject; base the comparison on the downstream region measurements and not just on image similarity. Then reconstruct the undersampled test cases with both methods using the supplied masks and report the downstream values. Established libraries are welcome; write the connecting code yourself.

predict.py and classical_recon.py must be standalone entrypoints, because I will run both of them again on further undersampled subjects. Please return the reconstructions, the results file, the split, runnable code with the trained weights, a comparison figure, an environment record and a README that states which method you recommend for this purpose, how you validated that choice and what the limitations are. Allow about an hour.
~~~

The full specification is in task.example.json. code/ holds the generator, grader, reference solution and control scripts of the example instance; VALIDATION.md lists how the reference and the controls scored.

