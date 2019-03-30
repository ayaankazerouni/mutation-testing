# mutation-testing

Enable automated mutation testing using the following:
- [x] PIT
- [x] muJava

## Overview
### [PIT](https://pitest.org)

Usage: [`./pit_runner.py --help`](pit/pit_runner.py)

[pit/pit_runner.py](pit/pit_runner.py) runs PIT with four possible sets of operators:
* `default` set (according to PIT website)
* our approximation of Offutt's `deletion` set 
* our approximation of Offutt's `sufficient` set
* `all` PIT operators evaluated in Laurent et al.'s 2017 paper

### [muJava](https://cs.gmu.edu/~offutt/mujava/)
Since muJava runs on Java 8, we use Docker to generate and test these mutants.

Usage: [`./mujava_runner.py --help`](mujava/mujava_runner.py)

See also [mujava/run-docker.sh](mujava/run-docker.sh)
