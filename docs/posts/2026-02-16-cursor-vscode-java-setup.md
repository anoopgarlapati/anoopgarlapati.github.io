---
title: Setting up Cursor and VS Code for Java projects
date: 2026-02-16
---

This covers configuring Cursor and VS Code for Java development — recommended settings, running and debugging tests, and viewing test results and coverage.

While this guide is aimed at Cursor, the same steps work for VS Code. If you don't have Cursor, VS Code with GitHub Copilot gives a similar AI-assisted experience.

# Prerequisites

- JDK
- Maven
- [Cursor](https://cursor.com/) or [VS Code](https://code.visualstudio.com/)

# Install Extension Pack for Java

1. Open the Extensions view from the Primary Side Bar, or use `Cmd+Shift+P` (macOS) / `Ctrl+Shift+P` (Windows/Linux) and search for **View: Show Extensions**.
2. Search for **Extension Pack for Java** from publisher `vscjava` / `microsoft.com`.
3. Install it. This pulls in:
   - **Language Support for Java** by Red Hat — workspace compilation, IntelliSense, navigation, refactoring (uses Eclipse JDT)
   - **Debugger for Java** — run and debug
   - **Test Runner for Java** — view and run JUnit and TestNG tests
   - **Maven for Java** — Maven project support
   - **Gradle for Java** — Gradle project support
   - **Project Manager for Java** — project view

# Recommended User Settings

Add these to **User Settings**, not workspace settings, so they apply to every Java project you open.

Open Command Palette (`Cmd+Shift+P`) and search for **Open User Settings (JSON)**.

| Setting | Recommended Value | Description |
| --- | --- | --- |
| `java.referencesCodeLens.enabled` | `true` | Show "N references" above classes and methods. |
| `java.implementationCodeLens` | `all` | Show "Implementations" above interfaces and abstract methods. |
| `java.compile.nullAnalysis.mode` | `disabled` | Disable null analysis to avoid cluttering the editor with warnings in large existing codebases. |
| `java.format.settings.url` | `/path/to/your/eclipse-formatter.xml` | Path to an Eclipse Formatter XML file for consistent code style. |
| `java.jdt.ls.vmargs` | `-XX:GCTimeRatio=4 -XX:AdaptiveSizePolicyWeight=90 -Dsun.zip.disableMemoryMapping=true -Xmx16G -Xms2G -Xlog:disable` | JVM args for the Java language server. Increasing `-Xmx` is recommended for large projects to keep the language server responsive. |
| `testing.coverageToolbarEnabled` | `true` | Shows the Testing Coverage Toolbar in the editor for toggling inline coverage. |
| `redhat.telemetry.enabled` | `false` | Disables telemetry for the Red Hat Java Language Server extension. |

Example `settings.json` (`~/Library/Application Support/Cursor/User/settings.json` on macOS):

```json
{
  "java.compile.nullAnalysis.mode": "disabled",
  "java.referencesCodeLens.enabled": true,
  "java.implementationCodeLens": "all",
  "java.jdt.ls.vmargs": "-XX:GCTimeRatio=4 -XX:AdaptiveSizePolicyWeight=90 -Dsun.zip.disableMemoryMapping=true -Xmx16G -Xms2G -Xlog:disable",
  "java.format.settings.url": "/path/to/your/eclipse-formatter.xml",
  "redhat.telemetry.enabled": false,
  "testing.coverageToolbarEnabled": true
}
```

**Notes:**

1. Ensure `~/.m2/settings.xml` has any required Maven repository mirrors configured so the IDE can resolve dependencies.
2. The IDE resolves Java based on `JAVA_HOME`. If it does not pick up the right JDK, add a `java.configuration.runtimes` entry in User Settings:

```json
"java.configuration.runtimes": [
  {
    "name": "JavaSE-17",
    "path": "/Library/Java/JavaVirtualMachines/openjdk-17.jdk/Contents/Home"
  }
]
```

## Known Issues

### `dependency:copy` fails on reactor artifacts (MDEP-187)

When using `maven-dependency-plugin:copy` to copy an artifact from another module in the same reactor build, the goal can fail with:

```
Artifact '...' has not been packaged yet (is a directory).
When used on reactor artifact, copy should be executed after packaging: see MDEP-187.
```

This happens because Maven resolves the reactor dependency as a project reference rather than a packaged artifact, and `dependency:copy` treats it as unpacked. See the [open bug on maven-dependency-plugin](https://github.com/apache/maven-dependency-plugin/issues/1180).

**Workaround:** If this build failure blocks the debugger, set the following in User Settings to allow the debugger to proceed regardless:

```json
"java.debug.settings.onBuildFailureProceed": true
```

# Testing

## Running Tests

### From the Test Explorer

1. Open the **Testing** view: `Cmd+Shift+P` → **View: Show Testing**.
2. Expand the project and navigate to the test package or class.
3. Click **Run** (play icon) or **Debug** (bug icon) next to a test class, method, or package.

You can also right-click a package, directory, or class in the Project Explorer and select **Run Tests** or **Debug Tests**.

### From the editor

- **Run:** Click the green play icon in the gutter next to a test method or class.
- **Debug:** Right-click the green play icon and select **Debug**.

## Debugging Tests

1. Set breakpoints by clicking in the gutter next to the line.
2. Start debugging using any of these:
   - Testing view → click **Debug** next to the test.
   - Editor → right-click the play icon → **Debug**.
   - Run and Debug view → choose a **Debug Test** configuration.

The Debugger for Java extension starts the test process with the debugger attached. Use the Debug toolbar (Continue, Step Over, Step Into, etc.) and the Variables, Watch, and Call Stack panels as usual.

## Attaching Debugger to a running process

To attach to a Java process already running with the debug agent:

1. Start the process with the JDWP agent:

```shell
java -agentlib:jdwp=transport=dt_socket,server=y,suspend=n,address=*:5005 -jar app.jar
```

2. In the **Run and Debug** view, create a `launch.json` and add an attach configuration:

```json
{
  "configurations": [
    {
      "type": "java",
      "name": "Attach to my-app",
      "request": "attach",
      "hostName": "localhost",
      "port": 5005
    }
  ]
}
```

3. Start your Java process on that port, then select the configuration in the Run and Debug view and click the green play button. The debugger attaches and you can set breakpoints and step through code normally.

## Viewing Test Results

- **Testing view:** Shows a pass/fail tree after a run. Click a test to navigate to the code; expand failures to see messages.
- **Test Results panel:** Bottom panel with pass/fail list and durations.
- **Terminal:** Raw test runner output (Surefire, TestNG, etc.).
- **Problems view:** Compilation errors and some test failures.

## Viewing Test Coverage

Run tests with coverage via the right-click menu on a test → **Run with Coverage**.

After the run, the **Test Coverage** panel opens in the sidebar. For inline coverage, open Command Palette → search **Test Coverage Toolbar** → toggle **Inline Coverage** to show or hide per-line coverage directly in the editor.

Both panels show coverage by statements, functions, and branches.

# Quick Reference

| Task | How |
| --- | --- |
| Run a command | `Cmd+Shift+P` and search by name |
| Search a file by name | `Cmd+P` and search |
| Run all tests in a class | Testing view → Run next to the class, or click the play icon in the editor gutter |
| Debug a single test | Set breakpoint → right-click play icon → Debug, or use Testing view |
| Attach debugger to JVM | Add an "Attach" config in Run and Debug view with the debug port; start the process on that port |
| Refresh Maven / fix unresolved types | `Cmd+Shift+P` → **Java: Clean Java Language Server Workspace** → Restart and delete → Reload |
| Language server slow / OOM | Increase `-Xmx` in `java.jdt.ls.vmargs` in User Settings |
