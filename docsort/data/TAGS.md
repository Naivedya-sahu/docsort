# Tag Vocabulary — single source of truth

Both `docsort` (validation) and the injected LLM system prompt read THIS file.
Edit a list here and the change flows to the script and the model — no other edits.
Format: inside each ```tags block, first whitespace token = the code; rest = description.

## STREAMS
```tags
CW    coursework / college degree material (B.Tech notes, assignments, lab)
GATE  GATE / competitive-exam prep — PYQs, test series, GATE-specific notes/formula books
PROJ  project deliverable — hardware/software build, capstone, prototype, project report
RES   research — papers, thesis, conference, datasets, literature review
REC   records / admin — marksheet, admit card, certificate, ID, exam form, fee receipt
REF   general reference — textbooks, standards, datasheets not tied to one course
```

## SUBJECTS
```tags
00MM   Math Methods — linear algebra, calculus, probability, transforms, numerical
01CA   Circuit Analysis — KCL/KVL, network theorems, RLC, two-port, transients
02SEMI Semiconductor Physics — carriers, bands, doping, drift/diffusion
03PN   PN Junction / Diodes — depletion, rectifier, zener
04BJT  BJT — bipolar biasing, CE/CB/CC, h-params
05MOS  MOSFET — CMOS, MOS cap, threshold, channel
06OPAMP Op-Amp — inverting, integrator, comparator, feedback
07ANLG Analog Circuits — amplifiers, oscillators, filters, LIC
08DIG  Digital / VLSI / Embedded — logic, FF, counters, verilog, microprocessor, ARM, FPGA
09SNS  Signals & Systems / DSP — fourier, laplace, z-transform, convolution, sampling
10CTRL Control Systems — transfer fn, bode, root locus, state space, stability
11COMM Communications / Networks — modulation, digital comm, info theory, antenna, radar
12EMAG Electromagnetics — maxwell, transmission line, waveguide, fields, smith chart
13TOOLS Programming / CAD / Tools — C/C++/python/matlab, kicad, simulation, lab software
90HUM  Humanities / Management / General — english, constitution, behaviour, management, ethics
91PHY  Physics (engineering/applied physics) — mechanics, optics, waves, modern physics, materials
92CHEM Chemistry (engineering chemistry) — bonding, electrochem, polymers, corrosion
NA     no single subject (use for PROJ/RES/REC/REF)
99UNS  unsure / multi-subject
```
> **Foundation/Common subjects** (not core-EE): `00MM` `90HUM` `91PHY` `92CHEM`.
> Add new ones here as they recur (see PROPOSALS below).

## PROPOSALS — how the taglist evolves
When the model meets a clear, recurring subject that is NOT in the list, it answers
`99UNS` plus a 5th token `PROPOSE:<LABEL>`. The script writes the file as
`[STREAM-~LABEL] name` — the **`~` is the review symbol** (these are NOT auto-moved).
Run `--review` to tally proposals; if a `~LABEL` shows up many times, promote it to a
real SUBJECT code here, then re-run. Example: many `~PHY` → added `91PHY` above.

## TYPES
```tags
notes
pyq
book
slides
assignment
lab
report
datasheet
syllabus
solution
misc
```

## FACETS (Obsidian tags applied later — NOT in the filename prefix)
```facets
source: #remarkable #scanned #handwritten #web
phase:  #sem1 #sem2 #sem3 #sem4 #sem5 #sem6 #sem7 #sem8 #masters #school
```
