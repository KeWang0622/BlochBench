# HW-02 · Spiral imaging with off-resonance correction

- Task ID: HW-02
- Legacy ID: v5-spiralb0

- Domain: Hardware, field and safety
- Tier: Core (v1.0 candidate); review status: pending
- Time cap: 60 min
- Instances recorded: 4 (instances.json)
- Automated checks (10): deliverables_present, sequence_hardware_limits, sequence_timing_contract, trajectory_coverage_contract, simulation_matches_replay, archive_metadata, public_field_map_accuracy, public_image_fidelity, report_consistency, hidden_rerun_correction

## Task (example instance)

~~~text
I would like an off-resonance-corrected spiral imaging experiment on a numerical test object, run entirely in simulation. Design a single-shot spiral-out gradient-echo sequence within the stated hardware limits, simulate the exported sequence with a Bloch simulator on the supplied object together with its off-resonance field, estimate a field map from the supplied dual-echo field-mapping scan, and reconstruct an image in which the off-resonance blurring and phase are removed.

All the specifications are in task.json: the gradient and RF limits, the echo time, the readout length and the k-space coverage contract, the object and its field convention, the field-mapping scan, the accuracy targets and the required files with their schemas. Pick established MRI software and install it yourself (for example Pulseq for the sequence and KomaMRI for the Bloch simulation) and write the code that joins the stages. The measurement data must come from a real Bloch simulation of the sequence file you export, including the object's field; do not replace it with a signal equation of your own.

reconstruct.py has to be a standalone program that needs only the measurement archive and the field-mapping scan. I will run it on data simulated from your sequence for a different object with a different field and its own field-mapping scan, so keep the sign conventions, time references, units and axis order consistent from start to finish.

Please send back the outputs, the code, a record of the software environment and a short README that explains how you validated the result and what its limits are, with a plot of the sequence waveforms and a figure that compares the uncorrected and corrected images with the field map. No scanner or in-vivo claims are needed; budget about an hour.
~~~

The full specification is in task.example.json. code/ holds the generator, grader, reference solution and control scripts of the example instance; VALIDATION.md lists how the reference and the controls scored.

