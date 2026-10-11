# Data

Put these files here (do not edit their property values):

- `Data.csv`: professor's dataset (1,552 rows)
- `Data_labelled.csv`: same rows plus `family`, `app_classes`, `basis`, `source`, `label_confidence` (training file)
- `Nonferrous_labels_verified.xlsx`: label sources for non-ferrous rows

Files written here by the notebook:

- `materials_clean.csv`: all 1,552 rows after cleaning (used by the engine)
- `unlabelled_scored.csv`: the 125 unlabelled ferrous rows scored by the model
