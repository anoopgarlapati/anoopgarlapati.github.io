---
title: G1 Garbage collector tuning
date: 2021-01-04
---

# Problem

We had been observing high CPU utilization due to frequent humongous allocation activity by G1 Garbage Collector in our Java web application. Also, after prolonged lifetime of a JVM instance, we observed this leading to frequent Full GC cycles as well.

# GC tuning

## Setting the minimum heap size

The first thing we noticed was that we were setting Xmx but not Xms. The [Oracle GC Tuning Guide](https://docs.oracle.com/javase/9/gctuning/garbage-first-garbage-collector-tuning.htm) recommends setting both to the same value:

> You can minimize heap resizing work by disabling it; set the options -Xms and -Xmx to the same value

This also matters because the initial value of the G1 heap region size is derived from the starting heap size, as noted [here](https://stackoverflow.com/a/48347022):

> G1 region-size in Java-8 is based on startingHeapSize/2048

We set Xms to the same value as Xmx in JVM startup options across all environments.

## Setting G1HeapRegionSize explicitly

The next lever was the heap region size. From the [Oracle G1GC article](https://www.oracle.com/technical-resources/articles/java/g1gc.html):

> If you see back-to-back concurrent cycles initiated due to Humongous allocations and if such allocations are fragmenting your old generation, please increase your -XX:G1HeapRegionSize such that previous Humongous objects are no longer Humongous and will follow the regular allocation path.

The [Plumbr handbook](https://plumbr.io/handbook/gc-tuning-in-practice/other-examples/humongous-allocations) explains the mechanics:

> The first solution for humongous allocation is to change the region size so that (most) of the allocations would not exceed the 50% limit triggering allocations in the humongous regions. The region size is calculated by the JVM during startup based on the size of the heap. You can override the size by specifying -XX:G1HeapRegionSize=XX in the startup script. The specified region size must be between 1 and 32 megabytes and has to be a power of two.

With Xms set equal to Xmx, the default heap region sizes worked out as follows:

| Environment | Min Heap size (Xms = Xmx) | Heap region size estimate = Xms/2048 | Actual heap region size (1 to 32 MB in powers of 2) | Humongous object size threshold (50% of heap region size) |
| --- | --- | --- | --- | --- |
| Performance | 4 GB | 2 MB | 2 MB | 1 MB |
| Staging | 1 GB | 0.5 MB | 1 MB | 0.5 MB |
| Pre-production | 4 GB | 2 MB | 2 MB | 1 MB |
| Preview | 4 GB | 2 MB | 2 MB | 1 MB |
| Production | 4 GB | 2 MB | 2 MB | 1 MB |

We then collected GC logs for 48 hours and filtered for humongous allocation events. The statistics for humongous object sizes observed across environments were:

| Environment | Min | Average | p90 | Max |
| --- | --- | --- | --- | --- |
| Performance | 0.5859 | 0.9207 | 0.9706 | 0.9707 |
| Staging | 0.5890 | 0.5890 | 0.5890 | 0.5890 |
| Pre-production | 0.5115 | 1.3707 | 1.9407 | 1.9412 |
| Preview | 0.5290 | 0.9533 | 1.2892 | 1.9407 |
| Production | 0.5000 | 0.8357 | 1.0002 | 1.0015 |

Note: All sizes are in MB.

Based on these numbers, the ideal heap region sizes to eliminate humongous allocations completely worked out to:

| Environment | Ideal heap region size (n) | New # of heap regions = Xms/n |
| --- | --- | --- |
| Performance | 2 MB | 2046 |
| Staging | 2 MB | 512 |
| Pre-production | 4 MB | 1024 |
| Preview | 4 MB | 1024 |
| Production | 4 MB | 1024 |

For simplicity and symmetry, we set the heap region size to 4 MB across all environments by adding `-XX:G1HeapRegionSize=4M` to JVM startup options.

## Identifying the humongous allocations

Beyond tuning the region size, we also wanted to understand what was actually causing these humongous allocations and whether they could be made smaller. As the [Plumbr handbook](https://plumbr.io/handbook/gc-tuning-in-practice/other-examples/humongous-allocations) notes:

> A more time-consuming but potentially better solution would be to understand whether or not the application can limit the size of allocations. The best tools for the job in this case are profilers. They can give you information about humongous objects by showing their allocation sources with stack traces.

We ran profilers against the application to identify the allocation sources and worked on reducing the size of the objects responsible for the bulk of the humongous allocations.
