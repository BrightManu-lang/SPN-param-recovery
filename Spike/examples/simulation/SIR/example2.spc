/**
 * Example configuration of branching
 */

// - line comment
/* 
   - block comment
*/
// Import - exactly one model
import: {   
    from: "./model/SIR-SPN.andl";
}



configuration: {

  model: {
    constants: {
      all: {
        // Branching: Scanning over model paramters
        k_infect_a: [[5.0e-5, 8.0e-5]];
      }
    }
    places: {
      // Branching: Scanning over model parameters
      SusceptiblePopulation_A: [[20000, 50000]];     
    }    
  }

  simulation:
  {

    /*
     * This is example variable that is added
     * to the log
     */
    varExample: model.places.SusceptiblePopulation_A;
    // Name of a simulation
    name: "SIR";
    /*
     * Branching:
     * Scanning over simulation types
     */
    type: [[
      // Stochastic simulation
      stochastic: {
        solver:
        direct: {
          threads: 1;
          runs: 3;
          //seed: 2413805201;
        }
        //single: true;// Single
        //avg: false;// Default set ot true
      },
      // Continuous Simulation
      continuous: {
        solver:
        BDF: {
          /*
           * Define new "runs" variable that
           * is used in the export file name
           */
          runs: "CONT";
          semantic: "adapt";// "bio", "adapt"
          iniStep: 0.1;
          // "CVDense", "CVSpgmr", "CVDiag", "CVSpbcg", "CVSptfqmr"
          linSolver: "CVDense";
          relTol: 1e-5;
          absTol: 1.0e-10;
          autoStepSize: false;
          reductResultingODE: true;
          checkNegativeVal: false;
          outputNoiseVal: false;
        }
      }
    ]];

    interval: 0:200:100;

    export: {
      // Array of places to save (if empty export all)
      places: [];//[];// all places
      //places:c: [];//[];// all coloured places
      //places:u: [];// uncoloured places
      transitions: [];// all transitions
      //transitions:c: [];// all coloured transitions
      //transitions:u: [];// all uncoloured transitions
      observers: [];
      csv: {
        sep: ";";// Separator  

        file: "./data/"
          << import.name << "_"
          << configuration.simulation.type << "_"
          << configuration.simulation.type.solver
          << "_" << configuration.simulation.type.solver.runs
          << "_" << configuration.model.constants.all.k_infect_a
          << "_"
          << configuration.model.places.SusceptiblePopulation_A
          << ".csv";// File name
      }
    }
  }
}

log: {
  sim.varExa: configuration.simulation.varExample;
}

