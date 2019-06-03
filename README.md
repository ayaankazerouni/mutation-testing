# mutation-testing

CLI tools to run mutation testing on large collections of assignment implementations. 
Mutation testing tools enabled:
* PIT
* \[EXPERIMENTAL\] muJava

## Overview
### [PIT](https://pitest.org)

Usage: [`./pit_runner.py --help`](pit/pit_runner.py)

[pit/pit-runner.py](pit/pit_runner.py) can PIT with different possible sets of operators:
* `default` set (according to PIT website)
* our approximation of Offutt's `deletion` set 
* our approximation of Offutt's `sufficient` set
* `all` PIT operators evaluated in Laurent et al.'s 2017 paper
* a custom set of operators, provided as CLI arguments

### Utilities

*`write_tasks.py`*

Writes tasks to an NDJSON file.
Tasks are just paths to projects where mutation testing is to be run.

Usage: [`./write_tasks --help`](write_tasks.py)

### **EXPERIMENTAL** [muJava](https://cs.gmu.edu/~offutt/mujava/)
Since muJava runs on Java 8, we use Docker to generate and test these mutants.

Usage: [`./mujava_runner.py --help`](mujava/mujava_runner.py)

See also [mujava/run-docker.sh](mujava/run-docker.sh)

