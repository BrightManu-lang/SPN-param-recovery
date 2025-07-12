/**
 * Example configuration of continuous simulation 
 */

// - line comment
/* 
   - block comment
*/
// Import - exactly one model
import: {   
    from: "./model/volterra.candl";
}


configuration: {

    model:
    /*
     * Two branches of model configuration
     */
    [[model_conf_A: {
        constants: {
          /*
           * Select global values set
           */
          valueset: "Main";
          /*
           * Scan over values sets
           */
          //valueset: [["Main", "V_Set_1", "V_Set_2", "V_Set_3", "V_Set_4"]];
          /*
           * Override model parameters if needed
           */
          all: {// The group name in CANDL model
              /*
               * Select values set for the group of constants
               */
              //valueset: "Main";
              RR1: 1;
              RR2: 0.1;
              RR3: 1;
              //RR: <1:?:2>
          }
        }
        /*
         * Override initial markings
         */
        places: {
          Prey: "40`a++30`b";
          Predator: "90`a++80`b";
        }

      },
      model_conf_B: {
              constants: {
                /*
                 * Select a values set
                 */
                valueset: "Main";
                /*
                 * Scan over values sets
                 */
                //valueset: [["Main", "V_Set_1", "V_Set_2", "V_Set_3", "V_Set_4"]];
                /*
                 * Override model parameters if needed
                 */
                all: {
                    RR1: 5;
                    RR2: 0.5;
                    RR3: 3;
                }
              }
              /*
               * Override initial markings
               */
              places: {
                Prey: "50`a++10`b";
                Predator: "10`a++50`b";
              }

            }
    ]];

    simulation:
    {
        name: "lotka_volterra"; // Name of a simulation
        /*
         * Stochastic simulation
         */
/*
        type: stochastic: {
          solver:
          tauLeaping: {
            // all
            threads: 2;
            runs: 10;
            // deltaLeaping
            delta: 0.1;
          }
        }
*/
        /*
         * Two branches of simulation configuration
         */
        type: [[continuous: {// -> cont // continuous, stochastic, hybrid
          solver:
            BDF: {
              semantic: "bio";// "bio", "adapt"
              iniStep: 0.1;
              linSolver: "CVDense";// "CVDense", "CVSpgmr", "CVDiag", "CVSpbcg", "CVSptfqmr"
              relTol: 1e-5;
              absTol: 1.0e-10;
              autoStepSize: false;
              reductResultingODE: true;
              checkNegativeVal: false;
              outputNoiseVal: false;
            }   
          },
          stochastic: {
            solver:
            tauLeaping: {
              // all
              threads: 2;
              runs: 5;
              // deltaLeaping
              delta: 0.1;
            }
          }
        ]];

        interval: 0:100:100;// start:spliting:end

        export: {
            // Array of places to save (if empty export all)
            places: [];//[];// all places
            //places:c: [];//[];// all coloured places
            //places:u: [];// uncoloured places
            transitions: [];// all transitions
            //transitions:c: [];// all coloured transitions
            //transitions:u: [];// all uncoloured transitions
            csv: {
              sep: ";";// Separator  
              file:  "./data/"
                    << name << "_"
                    << configuration.model << "_"
                    << configuration.simulation.type << "_"
                    << configuration.simulation.type.solver << "_"
                    //<< model.constants.all.RR1 << "_"
                    //<< model.constants.all.RR2 << "_"
                    //<< model.constants.all.RR3
                    << model.constants.valueset
                    << ".csv";// File name
            }
        }

    }
}



/**
 * Extra log
 */
///*
log: {
  simulation: configuration.simulation.name;
  valueset: configuration.model.constants.valueset;
  simulation_type: configuration.simulation.type;
  simulation_solver: configuration.simulation.type.solver;
  places_Prey: configuration.model.constants.places.Prey;

  all_in_on_line: "simulation: " << configuration.simulation.name
                  << " "
                  << " valueset: " << configuration.model.constants.valueset;
}

//*/
