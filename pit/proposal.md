# Selecting Practical Mutation Operators for Assessing Student-Written Test Suites 
**Rough proposal**

Possible submission targets: SIGCSE (due August) or ICSE SEET (due October)

---

## Problem Statement
We want to give students feedback on the quality of their test suites.
''Quality'' here refers to thoroughness or defect detection capability.
Currently existing methods are deficient in different ways.

**Code Coverage.**
Historically, we have used code coverage as a metric for test quality, but even strong forms of code coverage (like *object branch coverage* for Java) can be easily manipulated, and have been shown to not be inappropriate measures of test suite quality.

**All-Pairs Execution.**
Other researchers and educators have toyed with the idea of *all-pairs execution*, in which each student's project implementation is run against every other student's test suite.
First, the student implementations are run against an instructor-written test suite, to obtain ''ground-truth'' for the defects present in the implementation.  
Students are then graded on the proportion of others' defects that are detected by their test suites.
This has been shown to provide effective feedback, but comes with some deficincies:
* It requires that students program to a pre-determined interface, so that tests and solutions from different students can compile together
* It requires that all students have completed the project, precluding the possibility for incremental feedback
* It is susceptible to ''overzealous'' tests from students, and deficient tests from the instructor

**Mutation Testing.**
Mutation testing is a method of evaluating the thoroughness of a test suite in which defects, called *mutations*, are injected into programs to create faulty versions called *mutants*. 
The test suite is run against these mutants, and mutants are treated as *killed* if one or more tests fail directly because of the presence of the mutation.
A failing test case indicates that the mutant (or defect) was detected by failing test case. 
Then the test suite's *mutation score* is the proportion of mutants that are killed by the test suite.
Unfortunately, mutation testing is expensive to operationalise, since it involves repeatedly running the test suite against potentially many faulty versions of the program.

Extensive work has been done to reduce the cost of mutation testing.
Offutt et al. described a *sufficient* set of mutation operators, which is a set of 5 operators (of a possible set of 23) which achieve a high-level of fidelity when approximating the mutation score of a test suite, while producing 92% fewer mutants.
They further reduced the set of operators by only considering the *statement deletion* operator, which mutates by simply removing a statement at a time. 
These subsets result in considerable cost savings, while incurring acceptable losses in accuracy of mutation coverage.

## Work done so far

*This was the subject of the ICER paper that was recently rejected.* 

We used a statistical procedure to incrementally build a subset of mutation operators that best predicts coverage received using *all* mutation operators.
We used [PIT](http://pitest.org) for mutation testing, and collected coverage information on 2 subsets:

* `FULL`: All operators available in PIT
* `DELETION`: 8 operators that approximate the behaviour from Offut's Statement Deletion (SDL) operator (see [pit-runner.py](pit-runner.py) for details).

We used forward selection to select operators, choosing from the 8 operators in the `DELETION` set , since that can be considered the current 'state-of-the-art' in selective mutation.
We started with no operators, and then at each step we added the operator that most reduced BIC (Bayesian Information Criterion), stopping when BIC could reduce no further.
We ended up with:

* `REMOVE_CONDITIONALS`
* `NON_VOID_METHOD_CALLS`
* `TRUE_RETURNS`

At each step we analysed the additional cost introduced by the operators, and recommended that `REMOVE_CONDITIONALS` was the most cost-effective subset, since it predicted `FULL` coverage with $R^2=0.92$, and came with a 91% cost reduction.

## Proposal

The analysis described above was conducted on 50 submissions to Project 2 in the Fall 2016 semester of CS 3114.
It is possible that the results would not generalize to different contexts.
The context of our experiment can be defined with the following dimensions:

1. Assignment
2. Term
3. Course

I propose that we conduct the same experiment using data from all 4 assignments in Fall 2016 (generalising #1), and using data from the Fall 2018 semester (generalising #2).
I expect that results will generalise across these two dimensions.

To address dimension #3, I propose to carry out this experiment on submissions from CS 2114.
Projects in CS 2114 are considered simpler than those in CS 3114.

* **RQ1**: Is there really a difference between projects in the courses? How do we find out? We could use static analysis to characterise the programs based on cyclomatic complexity, class size, and similar features (this needs further thought). Can we make a 'common sense' argument? I.e., *It's an earlier course, so naturally the projects are less complex.* 
* **RQ2**: Does mutation operator subset selection result in a different subset for these projects than it does for projects in CS 3114? Can we explain the difference, if any?

