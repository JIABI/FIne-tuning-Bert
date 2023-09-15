# BERT-based Model Fine-Tuning for Spam Detection

This script fine-tunes a BERT-based model (like bert_uncased, bert_cased, Roberta) for the task of spam detection. 
The dataset used for this purpose appears to be `spamdata_v2.csv`.

## Features

- Supports both BERT and Roberta models.
- Utilizes GPU for training and evaluation.
- Allows setting of various parameters like model type, batch size, number of epochs option.
- Outputs a classification report for model evaluation.

## Prerequisites

- Python 3.x
- Libraries:
  - numpy
  - pandas
  - torch
  - sklearn
  - transformers

## Usage

```bash
python Fine_tuning_model.py --model [MODEL_TYPE] --batch_size [BATCH_SIZE] --epochs [EPOCHS]
```

### Arguments

- `--model`: Type of model to use (default: 'roberta-base'). Example values: 'roberta-base', 'bert-base-uncased' and 'bert-base-cased' from HuggingFace model collections, etc.
- `--batch_size`: Batch size for training (default: 32).
- `--epochs`: Number of training epochs (default: 10).

## Output

The script saves the trained model and appends the model's performance metrics to a file named `result.txt`.
