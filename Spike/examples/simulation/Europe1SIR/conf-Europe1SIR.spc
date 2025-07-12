/**
 * Example configuration of continuous simulation 
 */

// - line comment
/* 
   - block comment
*/
// Import - exactly one model
import: {   
    from: "./model/Europe1SIR-initMarkingUsingConstants.candl";
}


configuration: {

    model: {
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
        // The group name in CANDL model
        marking: [[
          AT: {
            I_m0AT: "V_m0AT/fraction";
            // For the rest, use default value from the model
//            I_m0BE: 0; 
//            I_m0CH: 0;
//            I_m0DE: 0;     
//            I_m0DK: 0;
//            I_m0ES: 0; 
//            I_m0FR: 0;
//            I_m0IT: 0;  
//            I_m0NL: 0;
//            I_m0PT: 0;
          },
          BE: {
            // Overide the default value of I_m0AT which is set in the model to: V_m0AT/fraction
            I_m0AT: 0;
            I_m0BE: "V_m0BE/fraction";
          },
          CH: {
            I_m0AT: 0;
            I_m0CH: "V_m0CH/fraction";
          },
          DE: {
            I_m0AT: 0;
            I_m0DE: "V_m0DE/fraction";
          },
          DK: {
            I_m0AT: 0;
            I_m0DK: "V_m0DK/fraction";
          },
          ES: {
            I_m0AT: 0;
            I_m0ES: "V_m0ES/fraction";
          },
          FR: {
            I_m0AT: 0;
            I_m0FR: "V_m0FR/fraction";
          },
          IT: {
            I_m0AT: 0;
            I_m0IT: "V_m0IT/fraction";
          },
          NL: {
            I_m0AT: 0;
            I_m0NL: "V_m0NL/fraction";
          },
          PT: {
            I_m0AT: 0;
            I_m0PT: "V_m0PT/fraction";
          },
          ALL: {
            I_m0AT: "V_m0AT/fraction";
            I_m0BE: "V_m0BE/fraction"; 
            I_m0CH: "V_m0CH/fraction";
            I_m0DE: "V_m0DE/fraction";
            I_m0DK: "V_m0DK/fraction";
            I_m0ES: "V_m0ES/fraction";
            I_m0FR: "V_m0FR/fraction";
            I_m0IT: "V_m0IT/fraction";
            I_m0NL: "V_m0NL/fraction";
            I_m0PT: "V_m0PT/fraction";
          }
        ]];
      }
    }


    simulation:
    {
        name: "Europe1SIR"; // Name of a simulation
        /*
         * Stochastic simulation
         */
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
              file: "./data/"
                    << name << "_"
                    << configuration.model.constants.marking << "_"
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

  all_in_on_line: "simulation: " << configuration.simulation.name
                  << " "
                  << " valueset: " << configuration.model.constants.valueset;
}

//*/
