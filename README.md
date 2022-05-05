# mutation-testing

Scripts to run mutation analysis on collections of student submissions to programming assignments. 
Mutation testing tools enabled:
* PIT
* \[EXPERIMENTAL\] muJava

## Overview
### [PIT](https://pitest.org)

Usage: [`./pit_runner.py --help`](pit/pit_runner.py)

[pit/pit-runner.py](pit/pit_runner.py) run PIT with different possible sets of operators:
* `default` set (according to PIT website)
* our approximation of Offutt's `deletion` set 
* our approximation of Offutt's `sufficient` set
* `all` PIT operators evaluated in Laurent et al.'s 2017 paper
* a custom set of operators, provided as CLI arguments

### [analysis](analysis)

Scripts and Jupyter notebooks used for analyses present in the paper

[_Fast and Accurate Incremental Feedback for Students' Software Tests Using Selective Mutation Analysis_](ayaankazerouni.github.io/publications#jss2021mutation). **Kazerouni**, Davis, Basak, Shaffer, Servant, Edwards. Journal of Systems and Software, 2021.

The paper's pretty long, so [an abridged overview of the main results is available.](https://ayaankazerouni.medium.com/fast-and-accurate-incremental-feedback-for-students-software-tests-using-selective-mutation-674bb2fc009c)

* [forward_selection.py](analysis/forward_selection.py): A simple implementation of forward selection using `statsmodels`. This was used in the `Core Study` in the paper above.
* [utils.py](analysis/utils.py): Various helper functions for wrangling mutation outcome data for analysis and plotting.

### Utilities

*`write_tasks.py`*

Writes tasks to an NDJSON file.
Tasks are just paths to projects where mutation testing is to be run.

Usage: [`./write_tasks --help`](write_tasks.py)

### **EXPERIMENTAL** [muJava](https://cs.gmu.edu/~offutt/mujava/)
Since muJava runs on Java 8, we use Docker to generate and test these mutants.

Usage: [`./mujava_runner.py --help`](mujava/mujava_runner.py)

See also [mujava/run-docker.sh](mujava/run-docker.sh)
