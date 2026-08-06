# Signature Detection Module

**Module:** CS402.3 Computer Graphics and Visualization
**Component:** Signature Detection
**Author:** Heshan De Silva
**Source files:** `src/detection/signature_detector.py`, `src/detection/signature_analyzer.py`

---

## 1. Responsibility

Given a photograph of an NSBM signing sheet, decide for every student row
whether a signature was written in the signature column. The module produces
the `signature_results` list that `AttendanceManager.record_attendance()`
consumes, and writes a progress image for each processing step so the report
can show the full pipeline.

The module deliberately does **not** read text. Identifying *which* student a
row belongs to is the OCR module's job; this module reports ink presence per
row position, and student numbers are attached from the ordered student list
that OCR supplies.

---

## 2. Processing pipeline

| # | Step | Technique | Why it is needed |
|---|------|-----------|------------------|
| 1 | Normalise | `cv2.resize` to 1600 px width, `INTER_AREA` | Phone images are 3024×4032. Fixing the width makes every morphological kernel size meaningful and cuts processing time by roughly 90%. |
| 2 | Grey-scale | `cv2.cvtColor(BGR2GRAY)` | Signatures are written in different pen colours (blue, black). Ink presence is a luminance question, not a colour one, so discarding colour removes a variable. |
| 3 | De-noise | `cv2.bilateralFilter(9, 75, 75)` | Suppresses JPEG and sensor noise while preserving the edges of thin pen strokes. A Gaussian blur would soften the strokes themselves. |
| 4 | Binarise | `cv2.adaptiveThreshold(GAUSSIAN_C, THRESH_BINARY_INV, block=25, C=15)` | Photographs carry strong, uneven shadows across the page. A global/Otsu threshold loses the shadowed corner; an adaptive threshold computes a local threshold per neighbourhood. `BINARY_INV` puts ink at 255 so ink becomes the foreground for morphology. |
| 5 | Estimate skew | `cv2.HoughLinesP`, median angle of segments within ±30° | Sheets are photographed hand-held, never square to the sensor. Measured skew on the five samples ranged from −2.27° to +1.67°. |
| 6 | Deskew | `cv2.getRotationMatrix2D` + `cv2.warpAffine(INTER_CUBIC, BORDER_REPLICATE)` | Directional morphology in step 7 only detects lines that are truly axis-aligned. Without this step, no table line is found at all. |
| 7 | Recover table rules | `cv2.morphologyEx(MORPH_OPEN)` with a `(W/25, 1)` kernel and a `(1, H/60)` kernel | Opening with a long, one-pixel-thin kernel keeps strokes that run a long way in one direction. Printed table rules survive; handwriting does not. |
| 8 | Find separators | Row/column pixel projection, thresholded and grouped | Converts the line masks into ordered lists of row and column positions — the table's geometry as numbers rather than pixels. |
| 9 | Isolate the student table | Longest run of near-uniform row gaps, then drop the short header band | The sheet holds two tables. The student table is the only block with many equal-height rows, which makes it identifiable without reading any text. |
| 10 | Isolate handwriting | `cv2.dilate` the grid, then `cv2.subtract` it from the binary image | Removes the printed borders so that an empty cell measures exactly zero ink instead of measuring its own frame. |
| 11 | Analyse each cell | `cv2.connectedComponentsWithStats` after a 2×2 opening | Yields ink ratio, stroke count and largest-stroke area per cell. |
| 12 | Decide | Ink ratio ≥ 0.010 **and** largest component ≥ 25 px | Two conditions rather than one: the ratio rejects near-empty cells, the component size rejects a single dust speck that happens to be dark. |

### Why the signature cells are computed, not contoured

The obvious approach is to find closed cell contours in the grid mask. It fails
here: students routinely sign **across** the printed cell border, and the
overlapping ink breaks the border into fragments, so adjacent signature cells
merge into one contour or disappear entirely. Deriving each cell as the
intersection of *global* row and column separators is immune to this, because a
broken border still leaves the rest of that rule intact elsewhere on the page.

---

## 3. Results on the five supplied sheets

Skew is the angle corrected in step 6. Ink is the fraction of the cell covered
by handwriting.

| Sheet | Skew | Row 1 | Row 2 | Row 3 | Row 4 | Row 5 | Row 6 | Present |
|-------|------|-------|-------|-------|-------|-------|-------|---------|
| 1.jpeg (31/05/2019) | +1.672° | 0.133 P | 0.062 P | 0.101 P | 0.085 P | 0.044 P | 0.043 P | 6/6 |
| 2.jpeg (21/06/2019) | −2.268° | 0.160 P | 0.108 P | 0.176 P | 0.112 P | 0.061 P | 0.116 P | 6/6 |
| 3.jpeg (28/06/2019) | −1.533° | 0.132 P | **0.000 A** | **0.000 A** | 0.104 P | 0.084 P | 0.128 P | 4/6 |
| 4.jpeg (05/07/2019) | −1.709° | 0.135 P | **0.000 A** | 0.046 P | **0.000 A** | 0.059 P | 0.052 P | 4/6 |
| 5.jpeg (12/07/2019) | −1.745° | 0.095 P | 0.093 P | 0.066 P | 0.088 P | 0.102 P | 0.133 P | 6/6 |

**Separation.** Signed cells measured between 0.043 and 0.176 ink ratio; unsigned
cells measured exactly 0.000. The decision threshold of 0.010 therefore sits in
a wide empty band, roughly four times below the weakest true signature. This is
why no sheet is close to a misclassification.

Detection matched visual ground truth on all 30 cells (5 sheets × 6 rows).

---

## 4. Challenges encountered

**Skew made table detection impossible at first.** The initial implementation
found zero cells on every sheet. The morphological opening in step 7 only keeps
strokes aligned to the kernel axis, and at 1.7° of rotation a 500-pixel-wide
table rule drifts about 15 pixels vertically — far more than the 1-pixel kernel
height. Adding Hough-based skew estimation before morphology took cell detection
from 0 to 41–43 cells per sheet.

**Signatures overwrite the cell borders.** Discussed in section 2; solved by
computing cells from global separators.

**An empty cell is not empty.** Before the grid subtraction in step 10, an
unsigned cell still contained its own printed frame and measured a non-zero ink
ratio comparable to a faint signature. Dilating the grid mask by one pixel
before subtracting also removes the anti-aliased halo either side of each
printed line.

**Distinguishing a header row from a student row.** The first band of the
student table is the printed `No / Student No / Title / Student Name /
Signature` header, and its dense printed text reads as a strong signature
(ink ratio 0.12–0.15). It is discarded either by keeping the last *N* bands
when the student count is known from `info.xml`, or by its height — the header
row is set in smaller type and is measurably shorter than the signature rows.

**OpenCV API drift.** `cv2.HoughLinesP` returns shape `(N, 1, 4)` under OpenCV 4
and `(N, 4)` under OpenCV 5. The code reshapes with `np.asarray(lines).reshape(-1, 4)`
so it runs unchanged on both.

---

## 5. Known limitations

**A hand-written annotation is not a signature.** On `2.jpeg`, row 6 contains
the lecturer's hand-written "ab" (absent) marking rather than a signature. Ink
is genuinely present, so the module reports the cell as signed, and the student
is recorded Present when they were in fact Absent. Ink-presence measurement
cannot resolve this by design — telling a signature apart from other handwriting
requires the shape-based recognition stage (`investigate.py`). This is the only
disagreement between the module's output and true attendance across all five
sheets.

**Row attribution near a boundary.** A signature written far enough above or
below its row can fall into a neighbouring cell. The 6-pixel padding trimmed
from each cell edge reduces this, but a signature drawn substantially outside
its row would still be misattributed.

**Severe perspective is not corrected.** Skew is corrected as a pure in-plane
rotation. A photograph taken at a steep angle would need a four-point
perspective transform, which is not implemented.

---

## 6. Public interface

```python
from src.detection import SignatureDetector

detector = SignatureDetector(save_progress=True)
outcome = detector.detect('data/sample_images/1.jpeg', students=student_list)

outcome['success']           # bool
outcome['skew_angle']        # float, degrees corrected
outcome['results']           # list consumed by AttendanceManager
outcome['progress_images']   # list of written PNG paths
```

Each entry of `results`:

```python
{
    'row_index': 0,
    'student_no': '10000409',
    'name': 'M S Dilshanika Perera',
    'signature_present': True,     # read by AttendanceManager
    'confidence': 1.0,
    'ink_ratio': 0.1333,
    'metrics': {...},
    'cell_box': (1107, 876, 240, 45),
}
```

`AttendanceManager.map_students()` requires only `student_no` and
`signature_present`; the remaining fields support the report and testing.

When the image-processing module supplies pre-cropped regions of interest, use
the alternative entry point instead:

```python
results = detector.detect_signatures(rois, students=student_list)
```

**Failure behaviour.** If the image is missing or the table cannot be located,
`detect()` returns `success: False` and marks every student **absent** rather
than raising. Marking absent is the conservative choice: a missed signature is
corrected by the lecturer, whereas a fabricated one silently records a student
as present.

---

## 7. Testing

`tests/test_detection.py` contains 45 tests: unit tests for the analyser
(blank cell, signed cell, single-speck noise, empty array, `None`, configurable
threshold), unit tests for the geometry helpers (projection grouping, uniform-run
selection, header-band removal, invalid table geometry), and integration tests
that run all five sheets against visually verified ground truth and assert the
output shape that `AttendanceManager` depends on.

```bash
python -m pytest tests/test_detection.py -v
```
