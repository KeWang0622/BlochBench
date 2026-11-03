# v8-sedwi

- Domain: Sequence design and Bloch simulation
- Tier: Core (v1.0 candidate); review status: pending
- Time cap: 60 min
- Instances recorded: 3 (instances.json)
- Automated checks (14): deliverables_present, sequence_readback, hardware_limits, raster_and_dead_times, rf_slice_selection_and_tr, sampling_contract, te_and_spin_echo_timing, b_values_from_waveforms, archive_b_values_match, bloch_replay, simulation_matches_replay, public_adc_map, hidden_rerun_adc, report_fields

## Task (example instance)

~~~text
Design a single-shot spin-echo echo-planar diffusion acquisition with one b = 0 volume and three diffusion-weighted volumes, export it as a Pulseq file, simulate that exported file on the supplied numerical object with an established Bloch simulator using the diffusion model stated in task.json, and fit an apparent-diffusion-coefficient map.

The hardware limits, timing and spin-echo conditions, the exact b-value definition and requirements, the sampling contract, the object description, the endpoint, the deliverables and the file schemas are all in task.json. Every number and convention there is binding; the design choices are yours. Choose and install suitable established tools yourself and write the code that connects them; do not replace the Bloch simulator with your own implementation.

Simulate the actual sequence.seq you deliver and fit from its actual simulated measurements. Make fit_adc.py a standalone entrypoint that works from the measurement archive alone, because it will be rerun on measurements of another object acquired with your sequence.

Return runnable code, the exported sequence, the output files listed in task.json, an environment record and a short README that explains how you computed and verified the b-values, timing and k-space sampling, how you checked the map, and what the limitations are. Show the waveforms. This is a simulation-only exercise with no scanner or patient claims. You have about 60 minutes.
~~~

The full specification is in task.example.json. code/ holds the generator, grader, reference solution and control scripts of the example instance; VALIDATION.md lists how the reference and the controls scored.

