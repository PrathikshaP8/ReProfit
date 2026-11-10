# Research results

This folder contains three figures generated from the existing ReProfit training outputs and SQLite database. Each figure is saved as a 400 dpi PNG and a vector PDF. No application code, model weights, datasets, or database records were modified.

## Figure 1 — AI model training and validation performance

Files: `ai_model_training_performance.png`, `ai_model_training_performance.pdf`

**Sources**

- Classification outputs: `backend/ml/runs/condition_yolo11/results.csv` and `backend/ml/runs/product_yolo11/results.csv`; run configurations are in the adjacent `args.yaml` files.
- Detection outputs: `backend/ml/runs/product_detector_ewaste_v7_quick_20261010_1327/results.csv`, `backend/ml/runs/laptop_screen_damage_v1_quick_20261010_1350/results.csv`, and `backend/ml/runs/laptop_screen_known_classes_20261010_1410/results.csv`; each has an adjacent `args.yaml`.
- Dataset identities and class names: the corresponding directories under `backend/ml/datasets`. Detection class names and Roboflow project/version are from each dataset's `data.yaml`.
- Training code: `backend/ml/train_condition_yolo11.py`, `train_product_yolo11.py`, `train_product_detector_yolo11.py`, and `train_laptop_damage_yolo11.py`.

**Metrics and sample counts**

- Classification panels show the per-epoch `metrics/accuracy_top1` (validation top-1 accuracy) and `train/loss` / `val/loss`. They do not show training accuracy because the saved classifier result files do not contain it.
- `condition_yolo11`: `yolo11n-cls.pt`, task `classify`, 12 saved epochs; the current matching `condition` folder has 5 source condition classes, 400 train image files and 80 validation files (all byte-unique within and between those two splits).
- `product_yolo11`: `yolo11n-cls.pt`, task `classify`, 30 saved epochs; the current matching `product` folder has 3 classes, 30 train files (26 unique image contents) and 12 validation files (12 unique contents). Four training files duplicate other training image contents, and one image content appears in both train and validation. The validation accuracy therefore has a known overlap limitation.
- Detection panels show saved validation precision, recall, mAP@0.50, and mAP@0.50:0.95 from `results.csv`. `product_detector_ewaste_v7_quick_20261010_1327` is the 36-class Roboflow `electronic-waste-dataset` v7 run: current matching data contains 3,788 train, 891 validation, and 381 test image files. Only 1 epoch is present in its CSV despite 2 configured epochs.
- `laptop_screen_damage_v1_quick_20261010_1350` uses the six-class Roboflow `laptop-screen-damage-detection-gzw1s` v1 dataset (648 train, 62 validation, 30 test files); one epoch is saved. `laptop_screen_known_classes_20261010_1410` uses its five-class known-label variant, with the same split counts and two saved epochs.
- SHA-256 content checks found no exact duplicate images across splits for the e-waste v7 or either laptop-screen dataset. The six-class and five-class laptop-screen dataset variants contain exactly the same image contents in each respective train, validation, and test split (648, 62, and 30 shared images). Their results are separate experiments on overlapping data, not independent replications.
- The current matching `condition` and `product` folder counts were checked against the saved metric granularity (80 and 12 validation examples respectively). Most run `args.yaml` files point to paths on other machines (the known-class detector uses a relative path), and no immutable training manifest was saved. Thus current-folder counts and hash checks describe the available local datasets, not a cryptographic proof of the exact historical bytes used by each run. In particular, the current condition trainer marks `condition` as the legacy painted dataset; this is not evidence of real-world condition performance. The current `condition_real` dataset directory is absent.

The plotted values are from training/validation output, not test performance. No independent test metrics were found in the saved evaluation outputs. Detector runs are short (one or two saved epochs); the figure preserves those run lengths rather than implying converged training. Other configured datasets without a corresponding saved `results.csv` were not plotted.

## Figure 2 — Approved return decision distribution

Files: `return_decision_distribution.png`, `return_decision_distribution.pdf`

**Source and denominator**

- Read-only query of `backend/reprofit.db`, `return_items` table. Schema is defined in `backend/models.py`; database initialization and the explicit seed row are in `backend/main.py`.
- The database contains 12 approved rows. One row marked `Seeded demo return item` was excluded. Of the remaining 11 approved rows, 8 have a recorded decision and 3 do not. Pending rows (8) are excluded; no rejected rows were included.
- Counts and percentages are calculated among the 8 non-demo approved records with a recorded decision: Resell 1 (12.5%), Refurbish 6 (75.0%), Recycle 1 (12.5%). The three approved rows without a decision are not assigned to a category.

## Figure 3 — Business and sustainability indicators

Files: `business_sustainability_impact.png`, `business_sustainability_impact.pdf`

**Sources, formulas, and sample counts**

- Uses the same 8 non-demo approved rows with a recorded decision and valid purchase and market prices from `backend/reprofit.db`.
- Per-return estimated profit is recomputed by calling `calculate_profit_breakdown` in `backend/services/profit_calculator.py` with the rates in the database's `settings` row. The current settings are 85% Resell recovery, 65% Refurbish recovery, 12% Refurbish repair cost, 8% Recycle recovery, and INR 0 other cost per item.
- Formula: `recovery value = market price × decision recovery rate`; for Refurbish only, `repair cost = market price × repair-cost rate`; `estimated profit = recovery value − purchase cost − repair cost − other costs`. The helper rounds each return's estimate to two decimal places before averaging.
- Among the 8 eligible estimates, 1 is positive and 7 are negative. The graph reports mean positive estimated profit as INR 31,909.23 (n=1), mean estimated loss as INR -10,188.74 (n=7), and the mean over all 8 estimates as INR -4,926.49. It recalculates instead of using stored `profit_estimate` values, which are not consistently aligned with the current formula/settings.
- The score panel averages stored `eco_score` and `sustainability_score` per decision category: Resell n=1, Refurbish n=6, Recycle n=1. The application's `services/ai_analyzer.py` maps eco scores to 95/82/62; `services/decision_engine.py` maps sustainability scores to 95/80/60.

These profit values are model estimates from configured assumptions, not realized cash flow or observed profit. Eco and sustainability values are project-defined decision scores; they are not measured emissions, material recovery, avoided waste, or other real-world environmental outcomes. Small category counts, especially n=1 for Resell and Recycle, limit generalization.
