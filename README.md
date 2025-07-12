# SPN-param-recovery

A simple **neural-network-driven** method for **recovering** the coefficients of covariate-dependent transition-rate functions in Stochastic Petri Net (SPN) models directly from noisy, partially observed event trajectories, without ever computing an explicit likelihood.

## Core Ideas

1. **Covariate-Dependent SPN parameter Posterior Approximation**  
Introduce a framework for inferring the coefficients of transition-rate functions in SPNs that explicitly depend on external covariates—without ever computing the likelihood. We train a lightweight 1D Convolutional ResNet to map observed token trajectories (with dropout) to a posterior over transition-rate function coefficients.  
2. **Likelihood-Free & Fast**  
   No expensive Bayesian sampling: inference is a multi-stochastic forward pass with Monte Carlo dropout for calibrated uncertainty bounds.  
3. **Robust to Missing Events**  
   On SPN trajectories with 20 % randomly dropped events, our surrogate achieves an RMSE of 0.108 on rate coefficients, while running orders of magnitude faster than traditional MCMC.  

## Simulation and Training
Simulation is done in SPIKE (software by Chodak https://www-dssz.informatik.tu-cottbus.de/DSSZ/Software/Spike). The SPN model file is in a `.andl` format and is run with the `.spc` configuration file. All these setup is embedded in the `Preprocess_Run_model_Simulation.ipynb` jupyter notebook. The only thing that needs to be changed in the jupyter notebooks are the file and folder paths. Everything else will run fine. However, since the model has been generated and converted to `.andl` format already. There is no need in running the create model cell.

To train and evaluate the neural surrogate model, just run the `nn_model_train_eval.ipynb` notebook. Our simulation is quite expensive (although Spike implementation runs relatively faster), training the neural network model straightaway with our pre-simulated data will be more efficient except additional samples are needed.

## Requirments

- Python 3.10 or newer
- This Spike version can only run on Windows

Python Packages:
- `numpy`, `pandas`, `matplotlib`
- `geopandas`
- `scipy`
- `sklearn`
- `torch`
