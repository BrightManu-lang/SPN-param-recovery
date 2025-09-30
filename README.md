# SPN-param-recovery

A simple **neural-network-driven** method for **recovering** the coefficients of covariate-dependent transition-rate functions in Stochastic Petri Net (SPN) models directly from noisy, partially observed event trajectories, without ever computing an explicit likelihood.

## Simulation
Simulation is done in SPIKE (software by Chodak https://www-dssz.informatik.tu-cottbus.de/DSSZ/Software/Spike). The SPN model file is in a `.andl` format and is run with the `.spc` configuration file. All these setup is embedded in the `Run_simulation.py` file. The only things that need to be changed in the script are the file and folder paths. Everything else will run fine.
The entire simulation are run in parallel with `30` processes at a time. This ensured very efficient computations.

## Training and Evaluation
All source code for training and evaluating our neural surrogate model for dropout rates `0.1` and `0.2` are located in the `model_src` folder. First, create a python environment and install the required packages using the `requirements.txt` file. Use this command to run the model in terminal, `python run_model.py` for the default run. If you want to set your own arguments, use `python run_model.py --epochs 100 --batch-size 16 --dropouts 0.1 0.3 0.5 --seed 42`. For each dropout rate, the `model_src` contains the saved best model and scaler. One can call that directly without going through the full training procedure.

We also provide a jupyter notebook that contains our hyperparamter tuning procedure in our quest to find the best dropout rate that could produce the best uncertainty calibration. Just open `model_dp_tune.py` run all to perform this procedure.

## Requirments

- Python 3.10 or newer
- This Spike version can only run on Windows

Python Packages:
- `numpy`, `pandas`, `matplotlib`
- `geopandas`
- `scipy`
- `sklearn`
- `torch`
- `joblib`
