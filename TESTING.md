# Testing the plugin

How to check the `ideastatica` plugin end to end, for Anthropic's directory reviewers and for
anyone who evaluates the plugin. Once IDEA StatiCa is installed, the tests take about 20
minutes.

## What you need

- **Windows with IDEA StatiCa 26.1**, from the
  [IDEA StatiCa downloads](https://www.ideastatica.com/product-downloads).
- **An IDEA StatiCa account with a license that includes the Connection API:**
  - Anthropic's directory reviewers: we provide a test account on request. Ask through the
    contact given in our directory submission.
  - Everyone else: the [14-day free trial](https://www.ideastatica.com/free-trial). Its terms
    do not allow commercial use.
- **The Connection REST API service running** and **Claude Code with the plugin installed**,
  as steps 1 and 2 of the [README](README.md) describe.

## Sample data

You need no files from us. The first project prompt gives Claude complete input data:
sections, materials, the end plate, welds, bolts and loads. IDEA StatiCa builds and calculates
the sample project from it, and the later prompts work on that project.

## Tests

Run the prompts in one Claude Code session, in this order. The project prompts save their
files in `C:\Temp\ideastatica-test`.

### 1. The service answers

> Is the IDEA StatiCa Connection REST API service running? Tell me its version.

Claude answers with the service version, for example `26.1.1.2809`.

### 2. Build and calculate a connection

> Create a new IDEA StatiCa Connection project with the EN design code: an HEB300 column and an
> IPE300 beam, both S 355, the beam framing into the column flange. Connect them with a
> 440 x 200 x 20 mm end plate, welded to the beam with fillet welds of 8 mm throat on the
> flanges and 5 mm on the web, and bolted to the column flange with eight M20 8.8 bolts in four
> rows at ±90 and ±185 mm, two columns 100 mm apart. Load the beam with 100 kN shear and a
> hogging moment of 80 kNm (top flange in tension), let IDEA StatiCa calculate it, save it as
> C:\Temp\ideastatica-test\end-plate-20mm.ideaCon and show me the check results IDEA StatiCa
> reports.

Claude writes and runs a script, the project file appears, and Claude lists the check results
(analysis, plates, bolts, welds) as IDEA StatiCa's results. In our runs, every check passed.

### 3. A change that fails

> Try a 6 mm end plate instead: let IDEA StatiCa recalculate, save it as
> C:\Temp\ideastatica-test\end-plate-6mm.ideaCon and tell me which checks IDEA StatiCa reports
> as failing.

Claude reports the checks that IDEA StatiCa marks as failing. In our runs, the analysis did not
reach the full load.

### 4. A search that IDEA StatiCa decides

> Find the thinnest end plate between 6 and 20 mm, in 2 mm steps, that IDEA StatiCa passes. Let
> IDEA StatiCa recalculate every thickness you try, then save the result as
> C:\Temp\ideastatica-test\end-plate-final.ideaCon.

Claude has IDEA StatiCa recalculate each thickness it tries and reports the thinnest one that
passes. In our runs, it was 8 mm.

### 5. An existing project and its report

> Open C:\Temp\ideastatica-test\end-plate-final.ideaCon, calculate it and save its PDF report as
> C:\Temp\ideastatica-test\end-plate-final.pdf.

The PDF report appears next to the project.

### 6. The same numbers in the desktop application

Open `end-plate-final.ideaCon` in IDEA StatiCa Connection and select **Calculate**. The check
results equal the ones Claude reported in test 4.

The exact numbers depend on the model Claude builds from the prompt. Test 6 is what matters:
Claude passes on IDEA StatiCa's numbers, so the desktop application shows the same ones.

## What to watch along the way

- Claude presents every check result as IDEA StatiCa's. It does not calculate, estimate or judge
  a check itself, and it marks its own engineering remarks as its own.
- The scripts talk only to the service on your computer, by default `http://localhost:5000`.
  The plugin has no hooks or MCP servers and runs nothing on its own.
- Claude does not start the service or restart it without asking you.

## Without IDEA StatiCa

Without the service, you can still check how the plugin loads and how it handles a missing
service:

1. `/plugin` lists **ideastatica** as installed, and typing `/ideastatica:` offers
   `connection-api`.
2. With no service running, ask the prompt of test 1. Claude reports that nothing answers at
   `http://localhost:5000`, explains how to start the service, and asks where it runs instead of
   trying other ports.
