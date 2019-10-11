FROM ubuntu:18.04

# variables
ARG BASEDIR="/usr/src/app"
ARG CLONEDIR="/tmp/mutation-testing"
ARG UID
ARG TASKFILE

# Install java, ant, python3, and pip
RUN \
  apt-get update && apt-get install -y \
    default-jdk \
    ant \
    python3 \
    python3-pip

# Python dependencies
RUN \
  python3 -m pip install pandas && \
  rm -rf /var/lib/apt/lists/*;

# directory to which to projects will be cloned
VOLUME ${CLONEDIR}

# directory containing source code and dependencies 
VOLUME ${BASEDIR}

WORKDIR ${BASEDIR}

# Create a user with the same UID as host user so we have permissions
RUN useradd -r -u ${UID} appuser
USER appuser

CMD ["bash", "-c", "./pit-runner.py tasks.ndjson -l -m REMOVE_CONDITIONALS > /usr/src/app/mutation-results.ndjson"]
# CMD ["bash", "-c", "./pit-runner.py tasks.ndjson -l -m all -c project1.DisplayCollection > /usr/src/app/mutation-results.ndjson"]
# CMD ["bash", "-c", "./pit-runner.py tasks.ndjson -l -m all -c game.SimpleArrayBag,game.SimpleLinkedBag > /usr/src/app/mutation-results.ndjson"]
# CMD ["bash", "-c", "./pit-runner.py tasks.ndjson -l -m all -c spacecolonies.ArrayQueue,spacecolonies.ColonyCalculator,spacecolonies.Person,spacecolonies.Planet,spacecolonies.Skills,spacecolonies.SpaceColonyDataException  > /usr/src/app/mutation-results.ndjson"]
# CMD ["bash", "-c", "./pit-runner.py tasks.ndjson -l -m all -c towerofhanoi.Disc,towerofhanoi.HanoiSolver,towerofhanoi.LinkedStack,towerofhanoi.Tower > /usr/src/app/mutation-results.ndjson"]
# CMD ["bash", "-c", "./pit-runner.py tasks.ndjson -l -m all -e p5-excludeGUI -t p5-excludeInputReference > /usr/src/app/mutation-results.ndjson"] 
