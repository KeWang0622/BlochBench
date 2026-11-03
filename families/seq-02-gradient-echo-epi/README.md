# SEQ-02 · Gradient-echo EPI with delay-robust reconstruction

- Task ID: SEQ-02
- Legacy ID: v8-epinav

- Domain: Sequence design and Bloch simulation
- Tier: Core (v1.0 candidate); review status: pending
- Time cap: 60 min
- Instances recorded: 3 (instances.json)
- Automated checks (12): deliverables_present, sequence_readback, hardware_limits, raster_and_dead_times, single_slice_selective_excitation, sampling_contract, te_and_echo_spacing, bloch_replay, simulation_matches_replay, hidden_delayed_rerun_reconstruct, public_image_and_report_ratios, report_fields

## Task (example instance)

~~~text
Design a single-shot gradient-echo echo-planar imaging acquisition, export it as a Pulseq file, simulate that exported file on the supplied numerical object with an established Bloch simulator, and reconstruct the image from the simulated measurements.

The hardware limits, the echo-spacing and echo-time definitions, the sampling contract, the gradient-delay model, the image-quality requirement, the object description, the deliverables and the file schemas are in task.json. Every number and convention there is binding; the design choices are yours. Choose and install suitable established tools yourself and write the code that connects them; do not replace the Bloch simulator with your own implementation.

Simulate the actual sequence.seq you deliver and reconstruct from its actual simulated measurements. Make reconstruct.py a standalone entrypoint that works from the measurement archive alone: it will be rerun on measurements of another object acquired with your sequence on hardware with an unknown gradient delay, so any reference data it needs must come from your sequence.

Return runnable code, the exported sequence, the output files listed in task.json, an environment record and a short README explaining how you verified timing, k-space coverage and the reconstruction, including a test of your reconstruction on deliberately delayed data, and what the limitations are. Show the waveforms and the image. This is a simulation-only exercise with no scanner or patient claims. You have about 60 minutes.
~~~

The full specification is in task.example.json. code/ holds the generator, grader, reference solution and control scripts of the example instance; VALIDATION.md lists how the reference and the controls scored.

