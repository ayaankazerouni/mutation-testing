# mutation-testing

Enable automated mutation testing using the following:
- [x] PIT
- [ ] muJava

## Overview
### [PIT](https://pitest.org)

**Dependencies**
Inside the [pit](pit/) directory, issue the following:
* `$ ./setup.sh`

This will download various jars required by PIT. Other dependencies:
* `sudo apt install ant` or `brew install ant`
* (on macOS) `brew install gsed`

Usage: `./pit_runner.py --help`

[pit/pit_runner.py](pit/pit_runner.py) runs PIT with three possible sets of operators:
* `default` set (according to PIT website)
* our approximation of Offut's `deletion` set 
* `all` PIT operators evaluated in Laurent et al.'s 2017 paper

### [muJava](https://cs.gmu.edu/~offutt/mujava/)
Since muJava runs on Java 8, we use Docker to generate and test these mutants.

**Dependencies**
Within the [mujava](mujava/) directory, issue the following command:
* `$ ./setup.sh`

This will download the various jars required by muJava. Other dependecies are taken care of in the [Dockerfile](mujava/Dockerfile).

