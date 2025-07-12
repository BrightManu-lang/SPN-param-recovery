# SPN-param-recovery

[![Build Status](https://img.shields.io/github/actions/workflow/status/you/spn-neural-surrogate/ci.yml)]()
[![License](https://img.shields.io/github/license/you/spn-neural-surrogate)]()

A simple **neural-network-driven** method for **recovering** the coefficients of covariate-dependent transition-rate functions in Stochastic Petri Net (SPN) models directly from noisy, partially observed event trajectories, without ever computing an explicit likelihood.

## Core Ideas

1. **Neural Posterior Approximation**  
   We train a lightweight 1D Convolutional ResNet to map observed token trajectories (with dropout) -> posterior over transition-rate coefficients.  

2. **Likelihood-Free & Fast**  
   No expensive Bayesian sampling: inference is a multi-stochastic forward pass with Monte Carlo dropout for calibrated uncertainty bounds.  

3. **Robust to Missing Events**  
   On SPN trajectories with 20 % randomly dropped events, our surrogate achieves an RMSE of 0.108 on rate coefficients, while running orders of magnitude faster than traditional MCMC.  
