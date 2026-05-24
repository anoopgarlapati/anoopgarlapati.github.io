---
title: Spring AOP - Writing good pointcuts
date: 2021-08-18
---
# Guide

During compilation, AspectJ processes pointcuts in order to optimize matching performance. Examining code and determining if each join point matches (statically or dynamically) a given pointcut is a costly process. A dynamic match means the match cannot be fully determined from static analysis and that a test is placed in the code to determine if there is an actual match when the code is running.

On first encountering a pointcut declaration, AspectJ rewrites it into an optimal form for the matching process. What does this mean? 

Basically, pointcuts are rewritten in DNF (Disjunctive Normal Form) and the components of the pointcut are sorted such that those components that are cheaper to evaluate are checked first. This means you do not have to worry about understanding the performance of various pointcut designators and may supply them in any order in a pointcut declaration.

However, AspectJ can work only with what it is told. For optimal performance of matching, you should think about what they are trying to achieve and narrow the search space for matches as much as possible in the definition. The existing designators naturally fall into one of three groups: kinded, scoping, and contextual:
- Kinded designators select a particular kind of join point: `execution`, `get`, `set`, `call`, and `handler`
- Scoping designators select a group of join points of interest (probably of many kinds): `within` and `withincode`
- Contextual designators match (and optionally bind) based on context: `this`, `target`, and `@annotation`

A well written pointcut should include at least the first two types (kinded and scoping). You can include the contextual designators to match based on join point context or bind that context for use in the advice. Supplying only a kinded designator or only a contextual designator works but could affect weaving performance (time and memory used), due to extra processing and analysis. Scoping designators are very fast to match, and using them usage means AspectJ can very quickly dismiss groups of join points that should not be further processed. A good pointcut should always include one if possible.

Usage of contextual designators (such as `@annotation`) alone is not recommended as they require dynamic match which results in significant performance overhead.

# Case Study
## Problem
In our application there was a goal to log execution time of a method for certain methods. This is a cross-cutting concern that needs to be addressed across several methods and hence having a naive solution such as using a clock/stopwatch in each method is cumbersome. The approach taken is to define an annotation that identifies all methods which need the execution time to be monitored. Since our application uses Spring framework, we can leverage Spring AOP support and implement an Aspect with Around advice.

The Pointcut expression initially we had was `@annotation(X)`. The expectation was that this would select all methods with annotation X and it did.

However, when testing the performance of the annotation and the aspect, we have an endpoint that usually completes in 180 ms and the response time of this endpoint shot up to 220 ms. Thats a 40 ms increase on 180 ms which is 22.22% increase. Not only that looks poor, the endpoint is /oauth/token endpoint which is a mission critical endpoint which we could not have any additional performance overhead.

We should achieve the original goal of logging execution time of methods using Spring AOP without any additional performance overhead.

## Cause
Digging deep into what could be the issue was when I found that my Pointcut expression is not optimal. I learned from an [old discussion in Spring framework issue](https://github.com/spring-projects/spring-framework/issues/9234) that `@annotation(X)` means dynamically match at any kind of join point where the subject of the join point has annotation X which is execution of a method or constructor or static initializer that has the annotation X, get of a field whose type has annotation X, set of a field whose type has annotation X, catch block for an exception whose type has annotation X. This was not what I intended.

Moreover, the Spring AOP documentation has a section on [writing good pointcuts](https://docs.spring.io/spring-framework/docs/current/reference/html/core.html#writing-good-pointcuts) which was also a good read which stated that `@annotation` PCD (Pointcut designator) is dynamically matched at runtime whereas PCD like `execution` is matched statically. Also, limiting the scope of Pointcut expression is crucial to its performance.

## Solution
Instead of using dynamically matched PCD `@annotation`, I switched to statically matched PCD of the form `execution(@X * *(..))` to select execution of any method returning any type taking any parameters that has the annotation X.

Also, I further narrowed down the scope of the pointcut expression from `execution(@X * *(..))` to `execution(@X * com.example.service..*.*(..))` which would select execution of methods having the annotation X within `com.example.service` package or its sub-packages. This change brought the response time of the token endpoint back to 180 ms with seemingly no change in performance degradation due to the aspect introduced.

# References
- Spring Framework Reference - [Writing good pointcuts](https://docs.spring.io/spring-framework/docs/current/reference/html/core.html#writing-good-pointcuts)
- Spring Framework Issue [#9234](https://github.com/spring-projects/spring-framework/issues/9234#issuecomment-453328064)