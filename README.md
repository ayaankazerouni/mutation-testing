# mutation-testing

Enable automated mutation testing using the following:
- [x] PIT
- [ ] muJava

## Overview
### PIT

**Dependencies**
From the [releases page](https://github.com/hcoles/pitest) of PIT, grab the latest versions of the following jars:
* pitest
* pitest-entry
* pitest-ant

Also grab a jar of JUnit from [maven](https://mvnrepository.com/artifact/junit/junit/4.12):
* junit

Usage: `./pit_runner.py --help`

[pit_runner.py](pit_runner.py) runs PIT with three possible sets of operators:
* `default` set (according to PIT website)
* our approximation of Offut's `deletion` set 
* `all` PIT operators evaluated in Laurent et al.'s 2017 paper

### muJava

TODO
