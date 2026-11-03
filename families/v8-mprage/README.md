# v8-mprage

- Domain: Sequence design and Bloch simulation
- Tier: Core (v1.0 candidate); review status: pending
- Time cap: 60 min
- Instances recorded: 3 (instances.json)
- Automated checks (14): deliverables_present, sequence_readback, hardware_limits, raster_and_dead_times, nonselective_rf, flips_and_timing, sampling_contract, bloch_replay, t1_null_at_kspace_centre, cycle_steady_state, simulation_matches_replay, hidden_rerun_reconstruct, public_image_and_report_ratios, report_fields

## Task (example instance)

~~~text
Design a three-dimensional MP-RAGE acquisition whose inversion time nulls tissue with a T1 of 0.78 s, export it as a Pulseq file, simulate that exported file on the supplied numerical object with an established Bloch simulator, and reconstruct the 3D image from the simulated measurements.

The hardware limits, the fixed readout train, cycle period and flip angles, the definition of the inversion time, the contrast and image requirements, the sampling contract, the object description, the deliverables and the file schemas are in task.json. Every number and convention there is binding; the inversion time and everything else not fixed there are yours to determine and justify. Choose and install suitable established tools yourself and write the code that connects them; do not replace the Bloch simulator with your own implementation.

Simulate the actual sequence.seq you deliver and reconstruct from its actual simulated measurements. Make reconstruct.py a standalone entrypoint that works from the measurement archive alone, because it will be rerun on measurements of another object acquired with your sequence.

Return runnable code, the exported sequence, the output files listed in task.json, an environment record and a short README that explains how you determined and verified the inversion time, the steady state, the k-space sampling and the image, and what the limitations are. Show the sequence waveforms and the image. This is a simulation-only exercise with no scanner or patient claims. You have about 60 minutes.
~~~

The full specification is in task.example.json. code/ holds the generator, grader, reference solution and control scripts of the example instance; VALIDATION.md lists how the reference and the controls scored.

