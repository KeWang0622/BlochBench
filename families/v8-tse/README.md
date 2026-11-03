# v8-tse

- Domain: Sequence design and Bloch simulation
- Tier: Core (v1.0 candidate); review status: pending
- Time cap: 60 min
- Instances recorded: 3 (instances.json)
- Automated checks (15): deliverables_present, sequence_readback, hardware_limits, raster_and_dead_times, flip_angles_and_slice_selection, sampling_contract, timing_te_esp_tr, bloch_replay, echo_train_phase_coherence, shot_steady_state, image_quality, simulation_matches_replay, hidden_rerun_reconstruct, public_image_and_report_ratios, report_fields

## Task (example instance)

~~~text
Design a two-dimensional multi-shot turbo spin-echo acquisition, export it as a Pulseq file, simulate that exported file on the supplied numerical object with an established Bloch simulator, and reconstruct the image from the simulated measurements.

All hardware limits, flip angles, timing definitions, the sampling contract, the echo-train, steady-state and image-quality requirements, the object description, the endpoint, the deliverables and the file schemas are in task.json. Every number and convention there is binding; how you meet the requirements is up to you. Choose and install suitable established tools yourself and write the code that connects them; do not replace the Bloch simulator with your own implementation.

Simulate the actual sequence.seq you deliver and reconstruct from its actual simulated measurements. Make reconstruct.py a standalone entrypoint that works from the measurement archive alone, because it will be rerun on measurements of another object acquired with your sequence.

Return runnable code, the exported sequence, the output files listed in task.json, an environment record and a short README that explains how you verified the timing, the k-space sampling, the echo train and the image, and what the limitations are. Show the sequence waveforms and the reconstructed image. This is a simulation-only exercise with no scanner or patient claims. You have about 60 minutes.
~~~

The full specification is in task.example.json. code/ holds the generator, grader, reference solution and control scripts of the example instance; VALIDATION.md lists how the reference and the controls scored.

