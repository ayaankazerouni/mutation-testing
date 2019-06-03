# Selecting Practical Mutation Operators for Assessing Student-Written Test Suites 
**Proposal for ICSE SEET (due in October)**

---

## Problem Statement
We want to give students feedback on the quality of their test suites.
''Quality'' here refers to thoroughness or defect detection capability.
Currently existing methods are deficient in different ways.

### Code Coverage 
Historically, we have used code coverage as a metric for test quality, but even strong forms of code coverage (like *object branch coverage* for Java) can be easily manipulated, and have been shown to not be inappropriate measures of test suite quality.

### All-Pairs Execution
Other researchers and educators have toyed with the idea of *all-pairs execution*, in which each student's project implementation is run against every other student's test suite.
First, the student implementations are run against an instructor-written test suite, to obtain ''ground-truth'' for the defects present in the implementation.  
Students are then graded on the proportion of others' defects that are detected by their test suites.
This has been shown to provide effective feedback, but comes with some deficincies:
* It requires that students program to a pre-determined interface, so that tests and solutions from different students can compile together
* It requires that all students have completed the project, precluding the possibility for incremental feedback
* It is susceptible to ''overzealous'' tests from students, and deficient tests from the instructor

### Mutation Testing 
Mutation testing is a method of evaluating the thoroughness of a test suite in which defects, called *mutations*, are injected into programs to create faulty versions called *mutants*. 
The test suite is run against these mutants, and mutants are treated as *killed* if one or more tests fail directly because of the presence of the mutation.
A failing test case indicates that the mutant (or defect) was detected by failing test case. 
Then the test suite's *mutation score* is the proportion of mutants that are killed by the test suite.
Unfortunately, mutation testing is expensive to operationalise, since it involves repeatedly running the test suite against potentially many faulty versions of the program.

Extensive work has been done to reduce the cost of mutation testing.
Offutt et al. described a *sufficient* set of mutation operators, which is a set of 5 operators (of a possible set of 23) which achieve a high-level of fidelity when approximating the mutation score of a test suite, while producing 92% fewer mutants.
They further reduced the set of operators by only considering the *statement deletion* operator, which mutates by simply removing a statement at a time. 
These subsets result in considerable cost savings, while incurring acceptable losses in accuracy of mutation coverage.

