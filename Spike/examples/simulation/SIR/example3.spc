/**
 * Example configuration of a stepwise simulation
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
        k_infect_a: 5.0e-5;
      }
    }
    places: {
      SusceptiblePopulation_A: 20000;
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
     * Set up a simulation
     */
    type:stochastic: {
      solver:
      direct: {
        threads: 1;
        runs: 3;
        //seed: 2413805201;
      }
      single: true;// Single
      //avg: false;// Default set ot true
    }
    
    interval: 0:200:100;

    /*
     * Stepwise simulation
     * Description: Depending on the current number of
     * infected specimens set restriction or relaxation
     * rules by applying change of infection kinetic rates
     * in a given time frame.
     */
    onStep: enabled: {
      /*
       * Kinetic prameters of
       * the restiction and relaxation
       * rules
       */
      k_infect_lo: 1.0e-9;
      k_infect_hi: 5.0e-5;

      k_infect:observe: constant.k_infect_a;
      iInitailSusceptiblePopulation_A: place.SusceptiblePopulation_A;
      iTimeFrame: 2;// Strech factor
      /*
       * Calcuate the window size that streach over
       * the full time frames defined by iTimeFrame
       */
      iWin: (interval.splitting / (interval.end - interval.start)) *
            iTimeFrame; 
      iWinStep: 0;
      bFirst: false;
      bRelax: false;
      dWinStepSize: 0;
      
      LOG = "END_INIT";
      /*
       * Smoothed stepwise lockdown and relaxation
       */
      do: {
        LOG = "step:" << simulation.step;
        LOG = "time:" << simulation.time;
        /*
         * Change infection rate if the number of
         * inceded specimens is > then 40% of susceptible
         * population
         */
        if(place.Infected_A > iInitailSusceptiblePopulation_A * 0.4
            && !bFirst) {
            
          bFirst = true;
          iWinStep = 0;
          // Distance & step size
          dWinStepSize = (constant.k_infect_a - k_infect_lo) / iWin;
          bRelax = false;
        }
        /*
         * Change infection rate if the number of
         * inceded specimens is < then 20% of susceptible
         * population
         */
        else if(place.Infected_A < iInitailSusceptiblePopulation_A *
                0.2 && !bRelax && bFirst) {
                
          iWinStep = 0;
          // Distance & step size
          dWinStepSize = (constant.k_infect_a - k_infect_hi) / iWin;
          bRelax = true;
        }
        // ABS - absolut value
        if(dWinStepSize < 0) {
          dWinStepSize = -dWinStepSize;              
        }
        /*
         * Adjust the kinetic parameter according
         * to the position in the time frame
         */
        if(iWinStep < iWin) {
          if(!bRelax) {
            constant.k_infect_a = constant.k_infect_a -
                                  dWinStepSize;
          } else if(bRelax) {
            constant.k_infect_a = constant.k_infect_a +
                                  dWinStepSize;
          }
          iWinStep = iWinStep + 1;
        }
        // Set the value of the observed variable
        k_infect = constant.k_infect_a;
        // Logging extra informations
        LOG = "bRelax: " << bRelax;
      }
    }

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

