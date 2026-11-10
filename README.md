# ReProfit Full Stack

ReProfit is an AI-powered reverse logistics profit recovery platform for e-commerce warehouses. It helps teams inspect returned products, run AI-style condition analysis, approve or reject recommendations, and track profit recovered through resell, refurbish, or recycle decisions.

## Stack

- Frontend: React 18, Vite, React Router v6, TanStack Query, Axios, Tailwind CSS, Recharts, Lucide React, React Hot Toast, dayjs
- Backend: FastAPI, SQLAlchemy, SQLite, Pydantic, Pillow

## Project Structure

```text
ReProfit_FullStack/
  frontend/
  backend/
  README.md
```

## Environment

Create `frontend/.env`:

```env
VITE_API_BASE_URL=http://localhost:8000/api
```

Create `backend/.env` for eBay Browse API access:

```env
EBAY_CLIENT_ID=your-ebay-app-id
EBAY_CLIENT_SECRET=your-ebay-cert-id
EBAY_ENVIRONMENT=production
EBAY_MARKETPLACE=EBAY_US
```

For immediate live shopping-price search, add a SerpApi key as well:

```env
SERPAPI_KEY=your-serpapi-key
```

Create the key at [serpapi.com](https://serpapi.com/). The Data Management page uses SerpApi Google Shopping results for live marketplace searches. Search results are fetched on demand and are not permanently synchronized; importing a result stores it in the ReProfit database. Keep `backend/.env` private.

Create an eBay developer application at [developer.ebay.com](https://developer.ebay.com/) and copy its App ID and Cert ID into this file. Keep `backend/.env` private and never put these values in the frontend. The Data Management page can search live eBay listings and import a selected listing into the return queue; purchase cost is entered manually because it is internal inventory data.

## Run Backend

```bash
cd backend
python -m pip install -r requirements.txt
python main.py
```

- API: [http://localhost:8000](http://localhost:8000)
- Docs: [http://localhost:8000/docs](http://localhost:8000/docs)

## Run Frontend

```bash
cd frontend
npm install
npm run dev
```

- App: [http://localhost:5173](http://localhost:5173)

## Model behavior

The backend uses the YOLO11 COCO object detector in `backend/yolo11n.pt` for product-image matching, not the condition classifier. Confident detector labels are normalized to canonical product families before comparison with the return item; a confident unrelated detected object is a mismatch, while no confident detection is unverified and cannot be approved. The existing laptop classifier is consulted only after the object detector independently detects a laptop, so its closed-set prediction cannot turn an unknown or unrelated image into a laptop match. The COCO checkpoint has no sandals class, so footwear it cannot confidently identify remains unverified rather than matching; a footwear-capable model is needed to confidently classify such images as mismatches.

The trained condition classifier is loaded from `backend/ml/weights/condition_yolo11.pt`. Its classes are `damaged`, `fair`, `good`, `like_new`, and `poor`; the assessment form maps `like_new` to `Good` and `poor` to `Bad` while keeping the model-derived score and confidence. If the trained model is unavailable, image assessment returns an error so the inspector can retry or continue with a manual assessment; it does not substitute a heuristic prediction. The classifier predicts an overall condition class and does not locate or identify specific defects such as cracks.

## Features

- Dark and light themes using CSS variables and persistent `localStorage`
- Dashboard KPIs, charts, recent decisions, notifications, and global search
- Return queue with AI analysis workflow and approve/reject actions
- Analytics with CSV export
- Decision engine thresholds with auto-processing preview
- Data management CSV import flow
- Live eBay Browse API product search and import
- Settings for company profile, notifications, API key, and webhook URL
- Seeded SQLite database with demo return inventory

## Roboflow dataset training (offline candidates)

The project has three distinct offline model roles: product object detection,
laptop visible-damage detection, and the existing condition classifier. The
Roboflow e-waste projects below are **object-detection** datasets, not
image-classification folders. Use `train_product_detector_yolo11.py` for
device-category boxes and `train_laptop_damage_yolo11.py` only for laptop
damage boxes. The existing `train_product_yolo11.py` remains the separate
folder-classification trainer for the small local classification dataset.
None of the new detector checkpoints are wired to live inference.

### Public Roboflow dataset inspection

The public Universe pages report CC BY 4.0 for all six projects. The
version/split counts and classes visible on the pages are:

| Dataset | Version to pin | Public task and counts | Public classes / notes | Use |
|---|---:|---|---|---|
| [E waste data](https://universe.roboflow.com/electronic-waste-ni0o1/e-waste-data/dataset/13) | 13 | Object detection; 13,279 total: 8,106 train / 2,768 valid / 2,405 test | The version page does not expose its class names; read `names` in the downloaded `data.yaml` before training. | Product detector candidate; class taxonomy still needs inspection. |
| [laptop screen damage detection](https://universe.roboflow.com/deeplearning-msmyh/laptop-screen-damage-detection-gzw1s/dataset/1) | 1 | Object detection; 740 generated: 648 train / 62 valid / 30 test. Project page separately reports 308 source images. | `crack`, `Normal`, `fade`, `lines`, `spot`, `undefined` (6). `undefined` and `Normal` need a deliberate keep/exclude decision; do not map them to another damage type. | Laptop damage detector candidate; clean/verify labels after export. |
| [test-project](https://universe.roboflow.com/laptop-damage-detection-trtwv/test-project-jrr6j) | 1 | Object detection; 741 train / 0 valid / 0 test; 247 source images. Its version applies 3 outputs per source example. | `mobile`, `glass_crack`, `in-display-pixel-defect` (3). | **Do not use for the laptop damage model**: it includes mobile-phone labels and has no validation/test split. |
| [Laptop_Damage_Identification](https://universe.roboflow.com/asset-damage-prediction/laptop_damage_identification/dataset/5) | 5 (latest) | Object detection; 4,881 total: 4,218 train / 467 valid / 196 test. | 29 project classes: `crack`, `Laptop`, `scratch`, `Scratch`, `Button`, `scratches`, `normal`, `Broken`, `chip`, `Adhesive-residue`, `Adhesive-residue-with-sticker`, `Broken Hinge`, `broken_button`, `broken_pixel`, `button-is-missing`, `chips`, `Damaged screen`, `deadpixels`, `depression`, `disassembled_laptop`, `fade`, `lines`, `lock`, `missing_button`, `missing_screw`, `problems_with_keys`, `screen`, `Screen`, `spot`. Case/plural synonyms need review, not automatic merging. | Laptop damage detector candidate; laptop-only class scope appears suitable, but verify downloaded labels. |
| [Balanced E-Waste Dataset](https://universe.roboflow.com/electronic-waste-detection/balanced-e-waste-dataset/dataset/3) | 3 (latest) | Object detection; 7,216 total: 4,994 train / 1,445 valid / 777 test. | 37 classes: `Laptop`, `Drone`, `Refrigerator`, `Oven`, `Microwave`, `Battery`, `Smartphone`, `Boiler`, `Blood-Pressure-Monitor`, `Clothes-Iron`, `Coffee-Machine`, `Computer-Keyboard`, `Computer-Mouse`, `Cooling-Display`, `Desktop-PC`, `Digital-Oscilloscope`, `Electric-Guitar`, `Electronic-Keyboard`, `Flashlight`, `Flat-Panel-Monitor`, `Flat-Panel-TV`, `Glucose-Meter`, `HDD`, `Music-Player`, `PCB`, `Photovoltaic-Panel`, `Projector`, `Rotary-Mower`, `Router`, `Server`, `Smoke-Detector`, `Straight-Tube-Fluorescent-Lamp`, `Street-Lamp`, `Telephone-Set`, `TV-Remote-Control`, `USB-Flash-Drive`, `Washing-Machine`. The project description says the source collection includes damaged devices; labels are device categories, not damage classes. | Best-defined broad product detector candidate; inspect whether its export contains box labels or segmentation polygons. |
| [electronic-waste-dataset](https://universe.roboflow.com/electronic-waste/electronic-waste-dataset/dataset/7) | 7 (latest) | Object detection; 5,060 total: 3,788 train / 891 valid / 381 test. | 37 classes shown: `mouse`, `phone`, `keyboard`, `remote`, `watch`, `fan`, `camera`, `calculator`, `10`, `11`, `13`, `16`, `17`, `18`, `2`, `22`, `23`, `3`, `6`, `8`, `blender`, `brush`, `car_key`, `cd`, `charger`, `digipen`, `earpods`, `headphone`, `mic`, `mvp`, `Object-Detection`, `pcb`, `pendrive`, `powerbank`, `razor`, `router`, `thermometer`. Numeric/unclear labels make this lower priority until class definitions are checked in its export. | Product detector candidate after taxonomy review. |

The linked e-waste and damage pages expose YOLOv8 and YOLOv11 exports; this
pipeline uses the YOLOv8 detection annotation format with a YOLO11 pretrained
model. For the e-waste-data v13 page, public metadata exposes counts/task but
not the classes, so its export's `data.yaml` is required to complete class
inspection. The public project pages were readable without signing in, but
Roboflow's SDK downloader requires an API key. Create/view it in Roboflow
Settings → API Key; keep it in the current shell environment only. Public
dataset export must also comply with each project's CC BY 4.0 license.

### Download pinned versions

From an interactive VS Code terminal, go to `backend`. The setup runner uses
Python's hidden `getpass` prompt, checks all six target directories before
asking for the key, then downloads datasets one-by-one and runs their assigned
`--validate-only` commands. It does not write the key to source, logs,
`.env`, or a file. Captured downloader output is redacted before display. It
stops at the first download error (including HTTP 401) and never replaces an
existing destination:

```powershell
cd C:\Users\Dell\Downloads\Reprofit_webapp\ReProfit-WebApp\ReProfit_FullStack\backend
python ml\setup_roboflow_datasets.py
```

At the hidden prompt, enter the new Private API Key. Do not paste it into
chat. Create/revoke keys at Roboflow Settings → API Key. The runner passes the
key only in the child downloader process environment and clears its local
reference afterward. If a download fails, it stops; completed prior datasets
remain in their version-specific folders. If the failed dataset left a partial
folder, inspect or move that folder yourself before rerunning—the setup will
not overwrite or delete it.

The runner downloads all six pinned YOLOv8 detection exports sequentially to
the following separate directories, including the known-incompatible
test-project so its labels can be inspected:

| Dataset version | Output directory |
|---|---|
| E waste data v13 | `backend/ml/datasets/roboflow_ewaste_v13` |
| Laptop screen damage v1 | `backend/ml/datasets/roboflow_laptop_screen_v1` |
| test-project v1 | `backend/ml/datasets/roboflow_test_project_v1` |
| Laptop Damage Identification v5 | `backend/ml/datasets/roboflow_laptop_damage_v5` |
| Balanced E-Waste v3 | `backend/ml/datasets/roboflow_balanced_ewaste_v3` |
| electronic-waste-dataset v7 | `backend/ml/datasets/roboflow_ewaste_v7` |

### Inspect downloaded annotations (no training)

The runner invokes the correct validator for every downloaded dataset. You can
rerun an individual check without training, for example:

```powershell
python ml\train_product_detector_yolo11.py --data ml\datasets\roboflow_balanced_ewaste_v3\data.yaml --validate-only
python ml\train_laptop_damage_yolo11.py --data ml\datasets\roboflow_laptop_damage_v5\data.yaml --validate-only
```

The shared detection validator prints the downloaded class names, per-split
train/validation/test image and annotation counts, and checks YOLO box and
polygon rows. Ultralytics detection training converts polygon-only label files
to their enclosing boxes; the validator reports those polygons separately and
rejects files that mix polygon and box rows because Ultralytics rejects that
format. Coordinates use Ultralytics' 1% normalization tolerance. The laptop
damage trainer rejects classes named `mobile`, `phone`, `smartphone`, or
`cellphone`; it will reject the third dataset for this reason. That project
also has no validation/test split, so its augmented training set must not be
randomly split after the fact. Do not merge damage datasets automatically:
the v1 screen data includes `Normal` and `undefined`, and the laptop damage
dataset has case/plural variants and other broad labels.

### Train isolated candidates

Only after the `--validate-only` output, labels, class meanings, and licensing
have been reviewed, start training explicitly:

```powershell
python ml\train_product_detector_yolo11.py --data ml\datasets\roboflow_ewaste_v13\data.yaml --name ewaste_v13_product_detector
python ml\train_product_detector_yolo11.py --data ml\datasets\roboflow_balanced_ewaste_v3\data.yaml --name balanced_ewaste_v3_product_detector
python ml\train_laptop_damage_yolo11.py --data ml\datasets\roboflow_laptop_screen_v1\data.yaml --name laptop_screen_damage_v1
python ml\train_laptop_damage_yolo11.py --data ml\datasets\roboflow_laptop_damage_v5\data.yaml --name laptop_damage_v5
```

Training writes `best.pt`, `last.pt`, metrics, and plots to a new directory
under `backend/ml/runs/`. The scripts validate `best.pt` on the validation
split after training and do not copy it to live inference paths or replace
existing weights. The existing folder classifier, condition model, and their
weights/runs are preserved. To evaluate with an untouched test split:

```powershell
yolo detect val model="ml/runs/balanced_ewaste_v3_product_detector/weights/best.pt" data="ml/datasets/roboflow_balanced_ewaste_v3/data.yaml" split=test
yolo detect val model="ml/runs/laptop_screen_damage_v1/weights/best.pt" data="ml/datasets/roboflow_laptop_screen_v1/data.yaml" split=test
```

Review per-class precision/recall, mAP50 and mAP50-95, confusion matrices,
false positives/negatives, and predicted boxes on representative real return
images. Preserve the test split for final evaluation; the scripts train and
validate but do not automatically use the test split. A checkpoint can only
be considered for live integration after class mapping and domain evaluation
are independently reviewed.

### Condition classifier training (separate candidate)

The production condition weights are not overwritten by this pipeline. Place
real, human-labeled condition images in `backend/ml/datasets/condition_real/`
using `train/<condition>/` and `val/<condition>/` folders. Accepted source
labels are `like_new`, `good`, `fair`, `poor`, and `damaged`; the trainer maps
them to `resell`, `refurbish`, and `recycle`. Keep all photos of one source
product in only one split. The trainer checks file hashes and source IDs for
train/validation leakage, oversamples minority classes in the staged training
copy, and writes a separate `condition_yolo11_candidate.pt`.

The painted dataset under `ml/datasets/condition/` is not a primary dataset.
If an optional synthetic augmentation dataset is provided, it contributes at
most 20% of the staged training examples and is used only for training:

```powershell
python ml\train_condition_yolo11.py --data ml\datasets\condition_real --device cpu
python ml\train_condition_yolo11.py --data ml\datasets\condition_real --synthetic-data ml\datasets\condition_synthetic --device cpu
python ml\evaluate_condition.py --weights ml\weights\condition_yolo11_candidate.pt --val ml\datasets\condition_real\val
```

Use `--device 0` when CUDA is available. Training uses pretrained YOLO11s
classification weights and stores its run and staged data under `ml/runs/`.
The evaluator writes a confusion matrix and reliability CSV, then fits a
validation NLL temperature to `ml/weights/temperature.json`; inference uses
that value when present. Evaluate the candidate on an untouched test set and
review per-class errors before any separately approved production promotion.
