---
name: sprocess-geometry-feature-extractor
description: Use this skill when the user wants to extract the outer boundary of a target Sprocess material within a rough ROI, then output ordered vertices plus automatically measured protrusion and recess features. This skill is for Sentaurus/Sprocess DF-ISE geometry analysis, especially spacer corners, tips, notches, and sidewall contour measurements.
---

# Sprocess Geometry Feature Extractor

This skill packages a reusable workflow for:

- extracting a target material or region boundary from an Sprocess-generated DF-ISE `.grd`
- limiting the search to a rough ROI
- ordering boundary points into a usable contour chain
- compressing the chain into geometric vertices
- automatically identifying protrusions and recesses
- reporting feature height/depth and width

## Use When

Use this skill when the user provides:

- a Sentaurus/Sprocess geometry mesh such as `n20_current_dfise.grd`
- a target material or region name
- a rough ROI like `xmin/xmax/ymin/ymax`

And wants:

- ordered contour points
- extracted vertices
- spike / protrusion information
- notch / recess information

## Inputs

Required inputs:

- `--grd`: DF-ISE mesh path
- `--target-region`: region name such as `Nitride_1.2`
- `--target-material`: material name such as `Nitride`
- `--xmin --xmax --ymin --ymax`: rough ROI

Optional inputs:

- `--groups`: manual feature-group file when automatic grouping should be overridden
- SSH alias / host and remote project path if running through the PowerShell wrapper

## Outputs

This skill produces:

- ordered candidate boundary points
- ordered turn vertices
- automatic protrusion / recess feature summary
- JSON and CSV outputs

Typical outputs:

- `*_ordered_vertices.json`
- `*_ordered_vertices.csv`
- `*_protrusion_recess_auto.json`
- `*_protrusion_recess_auto.csv`

## Core Files

- `scripts/extract_material_vertices.py`
  Generic region/material boundary extraction, ordering, and vertex compression.

- `scripts/measure_material_features.py`
  Automatic protrusion/recess measurement from ordered vertices.

- `scripts/invoke-remote-sprocess-geometry-feature-extractor.ps1`
  Uploads scripts to a remote Sentaurus VM and runs the workflow end-to-end.

## Recommended Workflow

1. Confirm the target DF-ISE `.grd` path.
2. Identify the target region and material names from the Sprocess structure.
3. Choose a rough ROI around the contour of interest.
4. Run `extract_material_vertices.py`.
5. Inspect the ordered vertices.
6. Run `measure_material_features.py`.
7. If the automatic feature grouping is slightly off, provide a manual group file and rerun.

## Automatic Feature Logic

The automatic feature measurement uses both:

- local slope / turning behavior
- physical position relative to a background edge

This is important because a true spike or recess is not defined by slope change alone.

For example:

- if a point protrudes mainly along `y`, the relevant background edge should be roughly horizontal, i.e. extending along `x`
- if a point protrudes mainly along `x`, the relevant background edge should be roughly vertical, i.e. extending along `y`

## Example Local Python Usage

```powershell
python extract_material_vertices.py \
  --grd /home/tcad/STDB/FDSOI_RLPX_v2/n20_current_dfise.grd \
  --target-region Nitride_1.2 \
  --target-material Nitride \
  --xmin -0.031 --xmax 0.0 --ymin 0.01 --ymax 0.0225 \
  --json-out nitride_vertices.json \
  --csv-out nitride_vertices.csv

python measure_material_features.py \
  --input nitride_vertices.json \
  --json-out nitride_features.json \
  --csv-out nitride_features.csv
```

## Example Remote Wrapper Usage

```powershell
powershell -ExecutionPolicy Bypass -File \
  "D:\个人知识库\skills\sprocess-geometry-feature-extractor\scripts\invoke-remote-sprocess-geometry-feature-extractor.ps1" \
  -HostAlias sentaurus-vm \
  -RemoteWorkDir /home/tcad/STDB/FDSOI_RLPX_v2/geometry_skill_run \
  -GrdPath /home/tcad/STDB/FDSOI_RLPX_v2/n20_current_dfise.grd \
  -TargetRegion Nitride_1.2 \
  -TargetMaterial Nitride \
  -XMin -0.031 -XMax 0.0 -YMin 0.01 -YMax 0.0225
```

## Validation Notes

- Always sanity-check whether the extracted contour belongs to the intended branch.
- Shared vertices across materials may appear on the boundary; this skill allows them when they include the target region/material.
- For highly irregular contours, the automatic feature detector may need a manual group file to lock onto the physically meaningful spike or recess.

## Practical Rule

Use automatic mode first.

If the automatic feature result is close but not perfect:

1. keep the extracted vertices
2. add a manual feature-group JSON
3. rerun only the feature measurement step
