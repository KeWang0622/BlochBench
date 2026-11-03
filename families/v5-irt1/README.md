# v5-irt1

- Domain: Sequence design and Bloch simulation
- Tier: Core (v1.0 candidate); review status: pending
- Time cap: 60 min
- Instances recorded: 4 (instances.json)
- Automated checks (11): deliverables_present, sequence_hardware_limits, sequence_timing_contract, trajectory_contract, periodic_state_preparation, simulation_matches_replay, archive_metadata, public_t1_accuracy, report_consistency, hidden_rerun_t1_accuracy, hidden_fit_only_accuracy

## Task (example instance)

~~~text
I would like a simulated T1-mapping experiment on a numerical test object: an inversion-recovery acquisition with a radial-spoke readout. Design the sequence, run the exported sequence through a Bloch simulator with the supplied object, reconstruct the undersampled radial data for each inversion time, fit a T1 map and report how accurate it is.

task.json contains everything required: the gradient and RF limits of the scanner, the inversion times, the recovery delay and the acquisition order, the radial sampling contract, the object, the accuracy targets and the list of required files with their schemas. The study is entirely simulated. Pick established MRI software and install it yourself (for example Pulseq for the sequence and KomaMRI for the Bloch simulation) and write the code that links the stages. The measurement data must come from a real Bloch simulation of the sequence file you export, not from a signal equation of your own, and every later stage must start from that file and those data.

reconstruct.py and fit_t1.py must be standalone programs that need only their input file. I will run reconstruct.py on data simulated from your sequence for another object, pass its output to fit_t1.py, and also run fit_t1.py on image sets I make myself, so keep the units, axis order, timing references and signal model consistent from start to finish.

Please send back the outputs, the code, a record of the software environment and a short README that explains how you validated the result and what its limits are, together with plots of the sequence waveforms and of the T1 map. No scanner or in-vivo claims are needed; budget about an hour.
~~~

The full specification is in task.example.json. code/ holds the generator, grader, reference solution and control scripts of the example instance; VALIDATION.md lists how the reference and the controls scored.

