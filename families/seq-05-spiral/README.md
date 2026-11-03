# SEQ-05 · Interleaved spiral acquisition and reconstruction

- Task ID: SEQ-05
- Legacy ID: v8-spiral

- Domain: Sequence design and Bloch simulation
- Tier: Core (v1.0 candidate); review status: pending
- Time cap: 60 min
- Instances recorded: 3 (instances.json)
- Automated checks (11): deliverables_present, sequence_readback, hardware_limits, raster_and_dead_times, rf_slice_selection_and_tr, sampling_contract_te_coverage, bloch_replay, simulation_matches_replay, hidden_rerun_reconstruct_with_delay, public_image_and_report_ratios, report_fields

## Task (example instance)

~~~text
Design an interleaved spiral-out gradient-echo acquisition under the stated gradient and slew limits, export it as a Pulseq file, simulate that exported file on the supplied numerical object with an established Bloch simulator, and reconstruct the image from the simulated non-Cartesian measurements.

The hardware limits, timing definitions, the sampling contract with its coverage requirement, the gradient-delay model, the image-quality requirement, the object description, the deliverables and the file schemas are in task.json. Every number and convention there is binding; the trajectory design and the reconstruction method are yours. Choose and install suitable established tools yourself and write the code that connects them; do not replace the Bloch simulator with your own implementation.

Simulate the actual sequence.seq you deliver and reconstruct from its actual simulated measurements. Make reconstruct.py a standalone entrypoint that works from the measurement archive alone, because it will be rerun on measurements of another object acquired with your sequence on hardware with a known, nonzero gradient delay recorded in the archive.

Return runnable code, the exported sequence, the output files listed in task.json, an environment record and a short README that explains how you verified the waveform limits, the trajectory and coverage, the delay handling and the image, and what the limitations are. Show the waveforms, the trajectory and the image. This is a simulation-only exercise with no scanner or patient claims. You have about 60 minutes.
~~~

The full specification is in task.example.json. code/ holds the generator, grader, reference solution and control scripts of the example instance; VALIDATION.md lists how the reference and the controls scored.

