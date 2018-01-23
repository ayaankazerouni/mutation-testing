#!/usr/bin/env perl
# Author: Jamie Davis <davisjam@vt.edu>
# Description:
#   - Perform a bunch of operations, using a cluster of worker nodes.
#   - To cleanly exit early, check the first few lines of stderr for a file to touch.

# Dependencies.
use strict;
use warnings;

use threads;
use threads::shared;
use Thread::Queue;

use JSON::PP;
use Getopt::Long;
use Time::HiRes qw( usleep );
use Carp;
use Data::Dumper;

# Auto-flush on stderr and stdout, to avoid weird buffering issues.
select(STDERR); $| = 1;
select(STDOUT); $| = 1;

# Globals.
my %globals;

my $LOG_LOCK : shared; # Logging.

my $WORKERS_DONE : shared; # Worker management.
$WORKERS_DONE = 0;

my $TASK_LOCK : shared; # Getting and delivering tasks.
my $tasksLoaded = 0;
my $TASKS : shared; # array ref

my $RESULT_LOCK : shared; # Emitting results.
my $RESULT_FH;
my $resultFHOpened : shared;
$resultFHOpened = 0;

my $exitEarlyFile = "/tmp/distributed-work-exit-early-pid$$"; # External signaling.
unlink $exitEarlyFile;
my $EXIT_EARLY : shared;
$EXIT_EARLY = 0;

my $NO_TASKS_LEFT = -1;

# Process args.
my $invocation = "$0 " . join(" ", @ARGV);
my %args;
GetOptions(\%args,
           "cluster=s",
           "workScript=s",
           "taskFile=s",
           "timeout=i",
           "resultFile=s",
           "workers=s@",
           "notWorkers=s@",
           "unusedCores=i",
           "copy=s",
           "env=s@",
           "verbose",
           "dryRun",
           "help",
          ) or die "Error parsing args\n";
%globals = &processArgs(%args);
&log("Invocation: $invocation");

my @workerNames = map { $_->{host} } @{$globals{cluster}};
&log(scalar(@{$globals{cluster}}) . " workers: <@workerNames>");

# Load tasks.
&log("Loading tasks from $globals{taskFile}");
$TASKS = shared_clone([&loadTasks("taskFile"=>$globals{taskFile})]);

&log("Opening resultFile $globals{resultFile}");
$RESULT_FH = &openResultFile($globals{resultFile});

# Start and await workers.
&log("Starting workers");
&log("To cleanly exit early, run the following command:\n  touch $exitEarlyFile");
&runWorkers("cluster"=>$globals{cluster});
&log("See results in $globals{resultFile}");
&noMoreResults();

# Write out any remaining tasks. 
if ($EXIT_EARLY) {
  &log("Exited early, writing out any remaining tasks");
  &writeOutRemainingTasks();
}

exit(0);

# Launch and await workers on all workers
#
# input: %args keys: cluster
sub runWorkers {
  my (%args) = @_;
  &assertUsage("runWorkers: Error, usage: hash with keys: cluster", $args{cluster});

  # Propagate copy
  if ($globals{copy_src} and $globals{copy_dest}) {
    &log("runWorkers: Propagating copy");
    &propagateCopyDir("src"=>$globals{copy_src}, "dest"=>$globals{copy_dest}, "destAccessCreds"=>$args{cluster});
  }

  # Start workers
  &log("runWorkers: Starting workers");
  my @my_threads;
  my $thread_exitEarly;
  for my $worker (@{$args{cluster}}) {
    my $unusedCores = &min($globals{unusedCores}, $worker->{logicalCores});
    if ($worker->{unusedCores}) { # Override global recommendation?
      $unusedCores = $worker->{unusedCores};
    }
    my $usedCores = $worker->{logicalCores} - $unusedCores;

    &log("runWorkers: Starting $usedCores processes on worker $worker->{host}, leaving $unusedCores unused cores");
    for my $core (1 .. $usedCores) {
      my %workerWithID = %{$worker};
      $workerWithID{id} = $core;
      &log("runWorkers: $workerWithID{host}:$workerWithID{id}");
      push @my_threads, threads->create(\&thread_worker, \%workerWithID);
    }
  }

  $thread_exitEarly = threads->create(\&thread_exitEarly, ($exitEarlyFile));

  &log("runWorkers: Waiting on my " . scalar(@my_threads) . " threads");
  for my $thr (@my_threads) {
    &log("runWorkers: thread finished!");
    $thr->join();
  }

  # If not already done, signal $thread_exitEarly.
  { lock($WORKERS_DONE);
    $WORKERS_DONE = 1;
  }

  &log("runWorkers: Waiting on thread_exitEarly");
  $thread_exitEarly->join();

  &log("runWorkers: Done");
  return;
}

sub getRemainingTasks {
  # Extract all remaining tasks.
  my @remainingTasks;
  while (1) {
    my $t = &getNextTask();
    last if ($t eq $NO_TASKS_LEFT);
    push @remainingTasks, $t;
  }

  my @strings = map { &task_toString($_) } @remainingTasks;
  &log("getRemainingTasks: Got " . scalar(@remainingTasks) . " remaining tasks: <@strings>");
  return @remainingTasks;
}

# input: ()
# output: ($anyRemainingTasks)
sub writeOutRemainingTasks {
  # A file to write to.
  my $remainingWorkFile = "/tmp/distributed-work-remainingWork-pid$$\.txt";
  unlink $remainingWorkFile;

  my @remainingTasks = &getRemainingTasks();
  if (@remainingTasks) {
    # Convert back to JSON and write out.
    my @lines = map { encode_json($_->{task}) } @remainingTasks;
    my $contents = join("\n", @lines);
    &writeToFile("file"=>$remainingWorkFile, "contents"=>$contents);
    &log(scalar(@remainingTasks) . " tasks remaining, see $remainingWorkFile");
  }

  return (0 < scalar(@remainingTasks));
}

# Thread.
# Get and do tasks until none remain, then return.
#
# input: ($worker) worker from &getClusterInfo, with extra key 'id' (1-indexed, core number on this worker)
# output: ()
sub thread_worker {
  my ($worker) = @_;

  my $tid = threads->tid();

  my $workerStr = "$worker->{host}:$worker->{id}";
  my $logPref = $workerStr;

  for (my $taskNum = 0; ; $taskNum++) {
    # Should we EXIT_EARLY?
    {
      lock($EXIT_EARLY);
      if ($EXIT_EARLY) {
        &log("$logPref: exiting early");
        return;
      }
    }

    # Get and complete a task.
    my $task = &getNextTask();
    if ($task eq $NO_TASKS_LEFT) {
      &log("$logPref: No tasks left");
      last;
    }
    &log("$logPref: task " . scalar(&task_toString($task)));

    my $out = &work("worker"=>$worker, "task"=>$task);
    &log("$logPref: completed task $task->{id}. Output: $out");
    my $result = { "task"=>$task, "worker"=>$workerStr, "output"=>$out };
    &emitResult($result);
  }

  return;
}

# input: %args: keys: src dest worker
# output: $dest
#
# Transfer the specified src
sub transferFile {
  my %args = @_;
  &assertUsage("transferFile: usage: src dest worker", $args{src}, $args{dest}, $args{worker});

  my ($out, $rc) = &cmd("scp -P$args{worker}->{port} $args{src} $args{worker}->{user}\@$args{worker}->{host}:$args{dest}"); 
  return $args{dest};
}

# input: %args: keys: file contents
# output: $file
sub writeToFile {
  my %args = @_;
  &assertUsage("writeToFile: usage: file contents", $args{file}, $args{contents});

	open(my $fh, '>', $args{file});
	print $fh $args{contents};
	close $fh;

  return $args{file};
}

# input: %args: keys: file
# output: $contents
sub readFile {
  my %args = @_;
  &assertUsage("readFile: usage: file", $args{file});

	open(my $FH, '<', $args{file}) or confess "Error, could not read $args{file}: $!";
	my $contents = do { local $/; <$FH> }; # localizing $? wipes the line separator char, so <> gets it all at once.
	close $FH;

  return $contents;
}

# input: (%args) keys: worker task
#  worker  the arg to thread_worker
#  task    created by &task_create
# output: ($task_stdout)
sub work {
  my %args = @_;
  &assertUsage("work: usage: worker task", $args{worker}, $args{task});

  my $tid = threads->tid();

  # Create task file.
  my $localTaskFile = "/tmp/distributed-map-$$\_$tid-LOCAL.json";
  my $remoteTaskFile = "/tmp/distributed-map-$$\_$tid-REMOTE.json";
  &writeToFile("file"=>$localTaskFile, "contents"=>encode_json($args{task}->{task}));
  &transferFile("src"=>$localTaskFile, "dest"=>$remoteTaskFile, "worker"=>$args{worker});
  unlink $localTaskFile;

  # Process task remotely and obtain stdout.
  # Use an intermediate file in case there are funny characters.
  # Use CPU affinity for maximum performance.
  my $remoteTaskStdoutFile = "/tmp/distributed-map-$$\_$tid";
  my $envString = join(" ", @{$globals{env}});
  my $tasksetID = $args{worker}->{id} - 1; # 1-indexed to 0-indexed
  my $taskset = "taskset -c $tasksetID";
  my $remoteCmd = "rm $remoteTaskStdoutFile; $envString $taskset $globals{workScript} $remoteTaskFile > $remoteTaskStdoutFile 2>/dev/null; rm $remoteTaskFile";
  my ($out, $timedOut) = &remoteCommand("accessCreds"=>$args{worker}, "command"=>$remoteCmd, "timeout"=>$globals{timeout});

  my $task_stdout = "";
  if ($timedOut) {
    &log("task timed out: " . encode_json($args{task}) . "\n");
  }
  else {
    my $localTaskStdoutFile = "$remoteTaskStdoutFile-local";
    &remoteCopy("src"=>$remoteTaskStdoutFile, "dest"=>$localTaskStdoutFile, "srcAccessCreds"=>$args{worker});
    ($task_stdout, my $rc) = &readFile("file"=>$localTaskStdoutFile);
    unlink $localTaskStdoutFile;
  }

  # Clean up
  unlink $localTaskFile;
  &remoteCommand("accessCreds"=>$args{worker}, "command"=>"rm $remoteTaskFile $remoteTaskStdoutFile > /dev/null 2>&1");

  return $task_stdout;
}

# Thread.
# Forever: Check whether we should exit early.
#          If so, set $EXIT_EARLY and then return.
#          Otherwise, if workers have finished ($WORKERS_DONE), return.
#
# input: ($exitEarlyFile)
# output: ()
sub thread_exitEarly {
  my ($exitEarlyFile) = @_;

  while (1) {

    # Exit early?
    if (-f $exitEarlyFile) {
      { lock($EXIT_EARLY);
        $EXIT_EARLY = 1;
      }
      last;
    }

    # Workers done?
    my $done;
    { lock($WORKERS_DONE);
      $done = $WORKERS_DONE;
    }
    if ($done) {
      last;
    }

    usleep(100*1000); # 100 ms
  }
}


# input: ($clusterFile)
# output: @cluster: list of node objects with keys: host user port logicalCores
sub getClusterInfo {
  my ($clusterFile) = @_;
  &assertUsage("getClusterInfo: Error, usage: (clusterFile)", $clusterFile);

  if (not -f $clusterFile or $clusterFile !~ m/\.json$/i) {
    die "getClusterInfo: Error, invalid clusterFile <$clusterFile>\n";
  }

  my ($out, $rc) = &readFile("file"=>$clusterFile);
  if ($rc) {
    die "getClusterInfo: Error, could not read clusterFile <$clusterFile>: $!\n";
  }

  my $cluster = eval {
    return decode_json($out);
  };
  if ($@) {
    die "getClusterInfo: Error parsing clusterFile <$clusterFile>: $@\n";
  }
  if (ref($cluster) ne "ARRAY") {
    die "Unexpected type of JSON object: " . ref($cluster) . " != ARRAY. clusterFile $clusterFile contents\n$out\n";
  }

  # We'll add some fields and otherwise manipulate it.
  my @cluster = @$cluster;

  # Confirm node definitions are valid.
  my $i = 0;
  for my $node (@cluster) {
    if (not &_isClusterNodeValid($node)) {
      die "getClusterInfo: Error, node $i is invalid (0-indexed)\n";
    }
    $i++;
  }

  # Discard non-pingable nodes
  my ($pingable, $notPingable) = &getPingableNodes("cluster"=>\@cluster);
  @cluster = @$pingable;
  if (@cluster) {
    if (@$notPingable) {
      &log("The following cluster nodes are not pingable: " . Dumper($notPingable));
    }
    else {
      &log("All cluster nodes are pingable");
    }
  }
  else {
    confess "Error, none of the nodes were pingable\n";
  }

  # Augment with a "logicalCores" field if none provided
  my $getNCores = sub { # returns nCores for a node
    my ($node) = @_;
    my ($out, $timedOut) = &remoteCommand("accessCreds"=>$node, "command"=>"nproc");
    my $nCores = -1;
		if ($out =~ m/^(\d+)$/) {
			$nCores = int($out);
		}
   return $nCores;
  };

  # Run getNCores in parallel and add a 'logicalCores' field to each node.
  my @cores = &threadMap("list"=>\@cluster, "func"=>$getNCores, "nThreads"=>scalar(@cluster));
  for (my $i = 0; $i < scalar(@cluster); $i++) {
    if ($cores[$i] < 0) {
      confess "Error, could not find number of cores on node $cluster[$i]->{host}\n";
    }
    $cluster[$i]->{logicalCores} = $cores[$i];
    &log("$cluster[$i]->{host} has $cluster[$i]->{logicalCores} logical cores");
  }

  return @cluster;
}

# input: ($clusterNode)
# output: ($isValid)
sub _isClusterNodeValid {
  my ($node) = @_;
  my @keys = ("host", "port", "user");
  if (not $node) {
    return 0;
  }
  
  for my $key (@keys) {
    if (not $node->{$key}) {
      return 0;
    }
  }

  return 1;
}

###
# Usage message, arg parsing.
###

sub getTerseUsage {
  my $terseUsage = "Usage: $0 --cluster C.json --workScript W --taskFile F
                             [--timeout S] [--resultFile R]
                             [--workers w1,...] [--notWorkers w1,...]
                             [--unusedCores N]
                             [--copy src:dest] [--env key=val,...]
                             [--verbose] [--dryRun]
                             [--help]
"; 
  return $terseUsage;
}


sub shortUsage {
  print STDOUT &getTerseUsage();
  exit 0;
}

sub longUsage {
  my $terseUsage = &getTerseUsage();

  print STDOUT "Description: Distribute tasks across workers
$terseUsage
  --cluster C.json                               JSON-formatted cluster of workers
                                                 Should be an array of \"node\" objects with minimal keys: host port user [logicalCores] [unusedCores]
                                                   host, port, user: suitable for passwordless ssh
                                                   [logicalCores]: skip query of node for # logical cores
                                                   [unusedCores]: override global --unusedCores
  --workScript W                                 Script to execute against each task
                                                 **Must exist on every worker**
                                                 Argument is a filename, its stdout is saved in resultFile
  --taskFile F                                   One task per line, JSON-encoded.
  [--timeout S]                                  Invoke workScript with a timeout of S seconds
  [--resultFile R]                               One result per line, NOT guaranteed in the same order
                                                 JSON-encoded.
  [--workers w1,... | --notWorkers w1,... ]      Workers to use | workers not to use
  [--unusedCores N]                              Cores to leave available on a worker
  [--copy src:dest]                              Copy src to dest on every worker before running workScript
                                                 Must be that src != dest. Can be a file or a dir.
  [--env key=val]                                Set these env vars when invoking workScript
                                                 If you have more than one env var, set them with separate --env args.
  [--verbose]
  [--dryRun]                                     Process args, print summary, and exit
  [--help]
Examples: $0 --cluster DY-cluster.json --workScript /tmp/sampleWorkScript.sh --taskFile sample/taskFile.json --copy sample/workScript.sh:/tmp/sampleWorkScript.sh
             Use DY-cluster.json, use a copy of sample/workScript.sh propagated to all workers, and work on the tasks in sample/taskFile.json
          $0 ... --env ECOSYSTEM_REGEXP_PROJECT_ROOT=/tmp/ecosystem-regexps --env 'PATH=/tmp/xxx:\$PATH'
             Set two environment variables when invoking workScript
";
}

# Process args after GetOptions, ensure validity, etc.
#
# input: (%args) from GetOptions
# output: (%globals) with keys:
#   cluster       listref of hashrefs representing nodes to use in the worker cluster
#   workScript    script to execute
#   taskFile      one task per line
#   resultFile    one result per line
#   timeout       0 means 'no timeout'
#   unusedCores   cores to leave idle on each worker
#   [copy_src     dir on manager]
#   [copy_dest    dir on worker]
#   [env          array ref of 'KEY=value' strings]
#   verbose       extra loud
sub processArgs {
  my %args = @_;
  my $invalidArgs = 0;

  # Bail out on no args or help.
  if (not scalar(keys %args)) {
    &shortUsage();
    exit 0;
  }

  if ($args{help}) {
    &longUsage();
    exit 0;
  }

  # cluster
  my @cluster;
  if ($args{cluster} and -f $args{cluster} and $args{cluster} =~ m/\.js(on)?$/i) {
    &log("Cluster file $args{cluster}");
    @cluster = &getClusterInfo($args{cluster});

    # workers
    if ($args{workers}) {
      $args{workers} = [split(",", join(",", @{$args{workers}}))]; # --w x,y --w z becomes x,y,z
    }
    else {
      $args{workers} = [map { $_->{host} } @cluster]; # Default to include all
    }

    # Filter in workers
    &log("Filtering in workers <@{$args{workers}}>");
    @cluster = grep { &listContains($args{workers}, $_->{host}) } @cluster;

    # notWorkers
    if ($args{notWorkers}) {
      $args{notWorkers} = [split(",", join(",", @{$args{notWorkers}}))]; # --w x,y --w z becomes x,y,z
    }
    else {
      $args{notWorkers} = []; # Default to exclude none
    }

    # Filter out notWorkers
    &log("Filtering out workers <@{$args{notWorkers}}>");
    @cluster = grep { not &listContains($args{notWorkers}, $_->{host}) } @cluster;

    my @survivingNames = map { $_->{host} } @cluster;
    if (@survivingNames) {
      &log("Using " . scalar(@cluster) . " workers <@survivingNames>");
    }
    else {
      &log("Error, no workers");
      $invalidArgs = 1;
    }
  }
  else {
    &log("Error, invalid cluster file");
    $invalidArgs = 1;
  }

  # workScript
  if ($args{workScript}) {
    &log("Using workScript $args{workScript}");
     # Can't use -f.
     # workScript might not exist *anywhere* yet before we honor --copy.
     # And this node might not be a worker so -f would still fail.
  }

  # taskFile
  if ($args{taskFile} and -f $args{taskFile}) {
    &log("Using taskFile $args{taskFile}");
  }
  else {
    &log("Error, invalid taskFile");
    $invalidArgs = 1;
  }
  
  # timeout
  if (defined $args{timeout}) {
    if ($args{timeout} <= 0) {
      $args{timeout} = 0;
    }
  }
  else {
    $args{timeout} = 0;
  }
  &log("Using timeout $args{timeout}");

  # resultFile
  if (not $args{resultFile}) {
    $args{resultFile} = "/tmp/distributed-map-pid$$-results";
  }
  unlink $args{resultFile};
  &log("Using resultFile $args{resultFile}");

  # unusedCores
  if (not defined $args{unusedCores}) {
    $args{unusedCores} = 0;
  }

  if (0 <= $args{unusedCores}) {
    &log("Using unusedCores $args{unusedCores}");
  }
  else {
    &log("Error, invalid unusedCores $args{unusedCores}");
    $invalidArgs = 1;
  }

  # copy
  my ($copySrc, $copyDest);
  if (defined $args{copy}) {
    my @spl = split(":", $args{copy});
    if (scalar(@spl) == 2) {
      my ($src, $dest) = @spl;
      if ($src ne $dest and -e $src) {
        &log("Using copySrc $src copyDest $dest");
        $copySrc = $src;
        $copyDest = $dest;
      }
      else {
        &log("Error, invalid copy src $src dest $dest. Must have src != dest, and src must exist");
        $invalidArgs = 1;
      }
    }
    else {
      &log("Error, malformed copy. Must be src:dest");
      $invalidArgs = 1;
    }
  }

  # env
  my @env;
  if (defined $args{env}) {
    @env = @{$args{env}}; # Do not do the ,-collapsing trick, because env vars might encode ,-delimited things
    &log("Env variables: @env");
  }

  # verbose
  if (not defined $args{verbose}) {
    $args{verbose} = 0;
  }

  # Error out on invalid args.
  if ($invalidArgs) {
    &shortUsage();
    exit 1;
  }

  my %globals = ("cluster"      => \@cluster,
                 "workScript"   => $args{workScript},
                 "taskFile"     => $args{taskFile},
                 "timeout"      => $args{timeout},
                 "resultFile"   => $args{resultFile},
                 "unusedCores"  => $args{unusedCores},
                 "copy_src"     => $copySrc,
                 "copy_dest"    => $copyDest,
                 "env"          => \@env,
                 "verbose"      => $args{verbose},
                );

  if ($args{dryRun}) {
    &log("End of dry run");
    exit 0;
  }

  return %globals;
}

###
# Task management.
###

# TODO If memory is a concern, we can read tasks line-by-line on-demand.

# input: (%args) keys: taskFile
# output: (@tasks)
#   Each elt contains a task from &task_create,
#    where the 'task' is a json-decoded version of one of the lines from the taskFile.
sub loadTasks {
  my %args = @_;
  &assertUsage("Usage: taskFile", $args{taskFile});

  lock($TASK_LOCK);
  return if ($tasksLoaded);
  $tasksLoaded = 1;

  my @taskLines = split("\n", &readFile("file"=>$args{taskFile}));
  chomp @taskLines;

  my $id = 0; # 1-indexed for sanity

  my @tasks;
  for my $line (@taskLines) {
    $id++;
    &log("Task line: <$line>") if $globals{verbose};

    my $task = decode_json($line);
    push @tasks, &task_create("id"=>$id, "task"=>$task);

    if ($id % 1000 eq 0) {
      &log("Loaded $id tasks");
    }
  }
  my $totalTasks = $id;

  &log("Total: $totalTasks tasks");

  return @tasks;
}

# Get the next task from @TASKS.
#
# input: ()
# output: ($task) or $NO_TASKS_LEFT
#   $task as created by &task_create.
sub getNextTask {
  lock($TASK_LOCK);
  &assert(($tasksLoaded), "getNextTask: Tasks never loaded");
  
  if (not @{$TASKS}) {
    return $NO_TASKS_LEFT;
  }

  my $nextTask = shift @{$TASKS};
  &log("getNextTask: got <" . &task_toString($nextTask) . ">, " . scalar(@${TASKS}) . " tasks remaining");
  return $nextTask;
}

# input: (%args) keys: id task
# output: ($task) a ref with keys: id task
sub task_create {
  my (%args) = @_;
  &assertUsage("task_create: usage: id task", $args{id}, $args{task});

  return { "id"    => $args{id},
           "task"  => $args{task},
         };
}

sub task_toString {
  my ($task) = @_;

  return "$task->{id}: " . encode_json($task->{task});
}

###
# Result management.
###

# input: ($resultFile)
# output: ($FH)
sub openResultFile {
  my ($resultFile) = @_;

  lock($RESULT_LOCK);

  if (not $resultFHOpened) {
    &log("emitResult: Opening $resultFile for results");
    open($RESULT_FH, ">", $resultFile) or confess "Error, could not open resultFile: $!\n";
    $resultFHOpened = 1;

    # Enable auto-flush for this handle to avoid weird buffering issues.
    my $curr = select;
    select($RESULT_FH); $| = 1;
    select($curr);
  }

  return $RESULT_FH;
}

# input: ($result) result object with keys: task workerInfo output
#   task: from &getNextTask
#   result: command-line output
# output: ()
sub emitResult {
  my ($result) = @_;

  lock($RESULT_LOCK);

  if (not $resultFHOpened) {
    confess "Error, must call openResultFile first\n";
  }

  my $encodedResult = encode_json($result);

  &log("emitResult: Emitting: <$encodedResult>");
  print $RESULT_FH "$encodedResult\n";

  return;
}

sub noMoreResults {
  if ($RESULT_FH) {
    close($RESULT_FH) or &log("Error, closing result_fh failed: $!");
  }
}

###
# Handle copy
###

# input: (%args) keys: src dest destAccessCreds 
#  destAccessCreds: array ref of hashrefs of destAccessCreds for use with remoteCopy
# output: ()
sub propagateCopyDir {
  my %args = @_;

  my @helpers;

  # Parallel propagation.
  my $propagate = sub {
		my ($cred) = @_;
		my $rc = &remoteCopy("src"=>$args{src}, "dest"=>$args{dest}, "destAccessCreds"=>$cred);
		return $rc;
  };
  my @results = &threadMap("list"=>$args{destAccessCreds}, "func"=>$propagate, "nThreads"=>scalar(@{$args{destAccessCreds}}));

  if (grep { $_ ne 0 } @results) {
    confess "Error, at least one copy failure: <@results>\n";
  }

  return;
}

###
# Utility
###

# input: (\@list, $e)
# output: true if $e is in @list, else false
sub listContains {
  my ($list, $e) = @_;
  for my $elt (@$list) {
    if ($elt eq $e) {
      return 1;
    }
  }

  return 0;
}

sub min {
  my (@nums) = @_;

  my $min = $nums[0];
  for my $n (@nums) {
    if ($n < $min) {
      $min = $n;
    }
  }

  return $min;
}

sub max {
  my (@nums) = @_;

  my $max = $nums[0];
  for my $n (@nums) {
    if ($max < $n) {
      $max = $n;
    }
  }

  return $max;
}

sub assert {
  my ($cond, $msg) = @_;
  if (not $cond) {
    print STDERR "ERROR: $msg\n";
    exit 1;
  }
}

# input: ($msg, @varsThatShouldBeDefined)
# output: ()
sub assertUsage {
  my ($msg, @shouldBeDefined) = @_;

  my @undefined = grep { not defined $_ } @shouldBeDefined;
  &assert((not @undefined), $msg);
}

# input: ($cmd)
# output: ($out, $rc)
sub cmd {
  my ($cmd) = @_;
  &log($cmd);
  my $out = `$cmd 2>&1`;
  return ($out, $? >> 8);
}

sub log {
  my ($msg) = @_;
  my $now = localtime;
  lock($LOG_LOCK);
  print STDERR "$now: $msg\n";
}

# input: (%args) keys: accessCreds command [timeout]
#  accessCreds: hashref, keys: port user host
#    hint: a worker object can be used as accessCreds
#  command:     string to execute over ssh
#  timeout: if > 0, enforce this timeout
# output: ($out, $timedOut)
sub remoteCommand {
  my %args = @_;
  &assertUsage("remoteCommand: Error, usage: hash with keys: accessCreds command", $args{accessCreds}, $args{command});
  if (ref($args{accessCreds}) ne "HASH") {
    confess "remoteCommand: Error, accessCreds is not a hashref\n";
  }

  my $timeoutPrefix = (defined($args{timeout}) and 0 < $args{timeout}) ?
                        "timeout $args{timeout}" : "";

  # Enforce timeout from the client end in case the command contains multiple commands ('x; y').
  my $cmd = "$timeoutPrefix ssh -p$args{accessCreds}->{port} $args{accessCreds}->{user}\@$args{accessCreds}->{host} '$args{command}'"; 
  my ($out, $rc) = &cmd($cmd); # rc is from ssh, not from command, so don't bother returning it.

  my $timedOut = ($timeoutPrefix and $rc eq 124);
  return ($out, $timedOut);
}

# Copy local file to remote host
# Recursively copy dirs
#
# input: (%args) keys: src dest [srcAccessCreds | destAccessCreds]
#  src/dest: files or dirs
#  [srcAccessCreds | destAccessCreds]: hashref, keys: port user host
#    Either src or dest can be remote, but not both
# output: ($rc) 0 success, non-zero failure
sub remoteCopy {
  my %args = @_;
  my $oneDefined = $args{srcAccessCreds} ? $args{srcAccessCreds} : $args{destAccessCreds};
  &assertUsage("remoteCopy: Error, usage: hash with keys: src dest [srcAccessCreds | destAccessCreds]", $args{src}, $args{dest}, $oneDefined);

  my $portArg = "";

  my $src = "";
  if ($args{srcAccessCreds}) {
    $portArg = "-P$args{srcAccessCreds}->{port}";
    $src = "$args{srcAccessCreds}->{user}\@$args{srcAccessCreds}->{host}:";
  }
  $src .= $args{src};

  my $dest = "";
  if ($args{destAccessCreds}) {
    $portArg = "-P$args{destAccessCreds}->{port}";
    $dest = "$args{destAccessCreds}->{user}\@$args{destAccessCreds}->{host}:";
  }
  $dest .= $args{dest};

  my $cmd = "scp -r $portArg $src $dest";
  my ($out, $rc) = &cmd($cmd); # rc is from ssh, not from command, so don't bother returning it.
  return ($rc);
}

# Apply a map operation in parallel
#
# input: (%args) keys: list func [nThreads]
# output: (@results)
#   @results = map { $func->($_) } @list
#   Ordering is preserved
sub threadMap {
  my (%args) = @_;
  &assertUsage("threadMap: Error, usage: hash with keys: list func [nThreads]", $args{list}, $args{func});
  my $nThreads = defined($args{nThreads}) ? $args{nThreads} : 8;

  # Fill q with shared copies of list elements
  my $q = Thread::Queue->new();
  my $i = 0;
  for my $task (@{$args{list}}) {
    my $sharedTask = { "id"   => $i,
                       "task" => $task
                     };
    $q->enqueue(shared_clone($sharedTask));
    $i++;
  }

  # Define a worker
  my $workerFunc = sub {
    my @results;
    while (defined(my $item = $q->dequeue_nb())) {
      my $result = $args{func}->($item->{task});
      push @results, { "id"     => $item->{id},
                       "result" => $result
                     };
    }
    return @results;
  };

  # Start and wait for workers
  my @threads;
  for (my $i = 0; $i < $nThreads; $i++) {
    push @threads, threads->create($workerFunc);
  }

  my @allResults;
  for (my $i = 0; $i < $nThreads; $i++) {
    push @allResults, $threads[$i]->join();
  }

  # Return results, sorted by id
  my @sorted = sort { $a->{id} <=> $b->{id} } @allResults;
  return map { $_->{result} } @sorted;
}

# input: (%args) keys: cluster
#   cluster: listref of hashrefs, see &getClusterInfo
# output: (\@pingableNodes, \@notPingableNodes) partition of @nodes
sub getPingableNodes {
  my (%args) = @_;
  &assertUsage("getPingableNodes: Error, usage: hash with keys: cluster", $args{cluster});

  my $isPingable = sub {
    my ($node) = @_;
    my $timeout = 1; # seconds
    my ($out, $rc) = &cmd("ping -c 1 -w $timeout $node->{host} > /dev/null 2>&1");
    return $rc == 0;
  };

  my @results = &threadMap("list"=>$args{cluster}, "func"=>$isPingable, "nThreads"=>scalar(@{$args{cluster}}));

  # Partition
	my (@pingable, @notPingable);
  for (my $i = 0; $i < scalar(@results); $i++) {
    if ($results[$i]) {
      push @pingable, $args{cluster}->[$i];
    }
    else {
      push @notPingable, $args{cluster}->[$i];
    }
  }

  return (\@pingable, \@notPingable);
}
