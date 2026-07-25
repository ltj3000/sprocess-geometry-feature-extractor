# Sprocess Geometry Feature Extractor

A reusable Sentaurus / Sprocess geometry-analysis toolkit for extracting a target material boundary from a DF-ISE `.grd`, converting the contour into ordered vertices, and automatically measuring protrusions and recesses.

This project is designed for workflows such as:

- spacer outer-boundary extraction
- sidewall tip and notch measurement
- local contour comparison across Sprocess runs
- automated geometry QA for TCAD structures

## What It Does

Given:

- a DF-ISE mesh file such as `n20_current_dfise.grd`
- a target `region` name
- a target `material` name
- a rough ROI: `xmin/xmax/ymin/ymax`

The toolkit can output:

- ordered boundary points for the target material
- compressed geometric vertices
- automatically detected protrusion / recess candidates
- feature height/depth and width
- JSON and CSV reports

## Repository Layout

```text
.
├── README.md
├── LICENSE
├── .gitignore
├── SKILL.md
├── examples
│   └── roi_example.json
└── scripts
    ├── extract_material_vertices.py
    ├── measure_material_features.py
    └── invoke-remote-sprocess-geometry-feature-extractor.ps1
```

## Core Scripts

### `scripts/extract_material_vertices.py`

Extracts the outer boundary of a target region/material from a DF-ISE `.grd` within a rough ROI.

Outputs include:

- ordered candidate contour points
- raw turn vertices
- compressed ordered vertices
- diagnostics CSV

### `scripts/measure_material_features.py`

Consumes the ordered vertices JSON and automatically detects protrusions and recesses.

The feature logic is not based on slope change alone.
It also considers the physical direction of the feature:

- if a point protrudes mainly along `y`, use a roughly horizontal background edge, i.e. one extending along `x`
- if a point protrudes mainly along `x`, use a roughly vertical background edge, i.e. one extending along `y`

This makes the measurement more physically meaningful for TCAD contours.

### `scripts/invoke-remote-sprocess-geometry-feature-extractor.ps1`

Convenience wrapper for running the full flow on a remote Sentaurus VM over SSH.

It will:

1. create the remote work directory
2. upload the Python scripts
3. run vertex extraction
4. run feature measurement

## Requirements

### Local

- Python 3
- PowerShell 5+ or PowerShell 7+
- SSH / SCP available in PATH if using the remote wrapper

### Remote

- Python 3 available on the Sentaurus VM
- access to the DF-ISE `.grd` file

## Example: Local Python Usage

```bash
python scripts/extract_material_vertices.py \
  --grd /home/tcad/STDB/FDSOI_RLPX_v2/n20_current_dfise.grd \
  --target-region Nitride_1.2 \
  --target-material Nitride \
  --xmin -0.031 --xmax 0.0 --ymin 0.01 --ymax 0.0225 \
  --json-out nitride_vertices.json \
  --csv-out nitride_vertices.csv

python scripts/measure_material_features.py \
  --input nitride_vertices.json \
  --json-out nitride_features.json \
  --csv-out nitride_features.csv
```

## Example: Remote PowerShell Usage

```powershell
powershell -ExecutionPolicy Bypass -File \
  "scripts/invoke-remote-sprocess-geometry-feature-extractor.ps1" \
  -HostAlias sentaurus-vm \
  -RemoteWorkDir /home/tcad/STDB/geometry_skill_run \
  -GrdPath /home/tcad/STDB/FDSOI_RLPX_v2/n20_current_dfise.grd \
  -TargetRegion Nitride_1.2 \
  -TargetMaterial Nitride \
  -XMin -0.031 -XMax 0.0 -YMin 0.01 -YMax 0.0225
```

## Example ROI File

See:

- `examples/roi_example.json`

## Input and Output Contract

### Input

Required:

- DF-ISE `.grd` path
- target region
- target material
- rough ROI

### Output

Typical files:

- `material_vertices.json`
- `material_vertices.csv`
- `material_features_auto.json`
- `material_features_auto.csv`

The vertex JSON contains:

- ordered boundary points
- ordered turn vertices
- component sizes
- diagnostics counts

The feature JSON contains:

- detected protrusions and recesses
- measurement direction
- chosen background edge type
- feature height/depth
- feature width

## Practical Notes

- The ROI should be rough, not ultra-tight.
- Shared vertices between materials are allowed if they include the target material/region.
- Very irregular contours may still need a narrower ROI to isolate the intended branch.
- Automatic feature detection is heuristic; for difficult cases, first verify the extracted vertices before trusting the feature report.

## Suggested Workflow

1. Start with a broad ROI around the contour of interest.
2. Run vertex extraction.
3. Inspect the ordered vertices.
4. Run automatic feature measurement.
5. If extra branches are included, tighten the ROI and rerun.

## Intended Use Cases

- Sentaurus Sprocess geometry inspection
- spacer contour metrology
- sidewall notch detection
- raised S/D corner comparison
- local geometry calibration support

## License

MIT
