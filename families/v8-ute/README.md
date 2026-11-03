# v8-ute

- Domain: Sequence design and Bloch simulation
- Tier: Core (v1.0 candidate); review status: pending
- Time cap: 60 min
- Instances recorded: 3 (instances.json)
- Automated checks (12): deliverables_present, sequence_readback, hardware_limits, raster_and_dead_times, rf_flip_slice_selection_tr, sampling_contract_te_coverage, half_pulse_pair_slice_profile, bloch_replay, simulation_matches_replay, hidden_rerun_reconstruct_short_t2, public_image_and_report_ratios, report_fields

## Task (example instance)

~~~text
Design a two-dimensional ultrashort-echo-time acquisition with half-pulse slice excitation and centre-out radial readouts, export it as a Pulseq file, simulate that exported file on the supplied numerical object with an established Bloch simulator, and reconstruct the image of the selected slice, including tissue with sub-millisecond T2.

The hardware limits, flip angle and repetition time, the echo-time limit, the pairing and sampling contract, the slice-profile, short-T2 and image requirements, the object description, the deliverables and the file schemas are in task.json. Every number and convention there is binding; the pulse and gradient design, the number of spokes and the reconstruction method are yours. Choose and install suitable established tools yourself and write the code that connects them; do not replace the Bloch simulator with your own implementation.

Simulate the actual sequence.seq you deliver and reconstruct from its actual simulated measurements. Make reconstruct.py a standalone entrypoint that works from the measurement archive alone, because it will be rerun on measurements of another object acquired with your sequence.

Return runnable code, the exported sequence, the output files listed in task.json, an environment record and a short README explaining how you verified the slice profile, echo time, trajectory, coverage and image, and what the limitations are. Show the waveforms, the slice profile and the image. This is a simulation-only exercise with no scanner or patient claims. You have about 60 minutes.
~~~

The full specification is in task.example.json. code/ holds the generator, grader, reference solution and control scripts of the example instance; VALIDATION.md lists how the reference and the controls scored.

