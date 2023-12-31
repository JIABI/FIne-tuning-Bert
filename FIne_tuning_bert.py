import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import transformers
from transformers import AutoModel, BertTokenizerFast, RobertaTokenizer, RobertaModel
import time
import argparse
from transformers import AdamW
from torch.utils.data import TensorDataset, DataLoader, RandomSampler, SequentialSampler
from train import BERT_Arch
parser = argparse.ArgumentParser()
parser.add_argument('--model', type=str, default='roberta-base', help='set model type')
parser.add_argument('--batch_size', type=int, default=32, help='set batch size')
parser.add_argument('--epochs', type=int, default=10, help='set number of epochs')
args = parser.parse_args()
# specify GPU
device = torch.device("cuda")
results_file_path = "result.txt"
# Load Dataset
df = pd.read_csv("spamdata_v2.csv")
df.head()
df.shape
# check class distribution
df['label'].value_counts(normalize = True)

# Split train dataset into train, validation and test sets
train_text, temp_text, train_labels, temp_labels = train_test_split(df['text'], df['label'],
                                                                    random_state=2018,
                                                                    test_size=0.3,
                                                                    stratify=df['label'])

# we will use temp_text and temp_labels to create validation and test set
val_text, test_text, val_labels, test_labels = train_test_split(temp_text, temp_labels,
                                                                random_state=2018,
                                                                test_size=0.5,
                                                                stratify=temp_labels)
def bert():
    if args.model == 'roberta-base':
        bert = RobertaModel.from_pretrained(args.model)
    else:
        bert = AutoModel.from_pretrained(args.model)
    # Freeze BERT Parameters
    for param in bert.parameters():
        param.requires_grad = False
    return bert
def load_model():
    # Import BERT Model and BERT Tokenizer
    # import BERT-base pretrained model
    # Load the BERT tokenizer
    if args.model == 'roberta-base':
        tokenizer = RobertaTokenizer.from_pretrained(args.model)
    else:
        tokenizer = BertTokenizerFast.from_pretrained(args.model)
    # sample data
    text = ["this is a bert model tutorial", "we will fine-tune a bert model"]
    # encode text
    sent_id = tokenizer.batch_encode_plus(text, padding=True, return_token_type_ids=False)

    # output
    print(sent_id)

    # Tokenization
    # get length of all the messages in the train set
    seq_len = [len(i.split()) for i in train_text]
    pd.Series(seq_len).hist(bins=30)
    max_seq_len = 25
    # tokenize and encode sequences in the training set
    tokens_train = tokenizer.batch_encode_plus(
        train_text.tolist(),
        max_length=max_seq_len,
        pad_to_max_length=True,
        truncation=True,
        return_token_type_ids=False
    )

    # tokenize and encode sequences in the validation set
    tokens_val = tokenizer.batch_encode_plus(
        val_text.tolist(),
        max_length=max_seq_len,
        pad_to_max_length=True,
        truncation=True,
        return_token_type_ids=False
    )

    # tokenize and encode sequences in the test set
    tokens_test = tokenizer.batch_encode_plus(
        test_text.tolist(),
        max_length=max_seq_len,
        pad_to_max_length=True,
        truncation=True,
        return_token_type_ids=False
    )
    # Convert Integer Sequences to Tensors
    # for train set
    train_seq = torch.tensor(tokens_train['input_ids'])
    train_mask = torch.tensor(tokens_train['attention_mask'])
    train_y = torch.tensor(train_labels.tolist())
    # for validation set
    val_seq = torch.tensor(tokens_val['input_ids'])
    val_mask = torch.tensor(tokens_val['attention_mask'])
    val_y = torch.tensor(val_labels.tolist())
    # for test set
    test_seq = torch.tensor(tokens_test['input_ids'])
    test_mask = torch.tensor(tokens_test['attention_mask'])
    test_y = torch.tensor(test_labels.tolist())
    return [train_seq, train_mask, train_y, val_seq, val_mask, val_y, test_seq, test_mask, test_y]


# Create DataLoader

# wrap tensors
train_test_result = load_model()
train_data = TensorDataset(train_test_result[0], train_test_result[1], train_test_result[2])

# sampler for sampling the data during training
train_sampler = RandomSampler(train_data)

# dataLoader for train set
train_dataloader = DataLoader(train_data, sampler=train_sampler, batch_size=args.batch_size)

# wrap tensors
val_data = TensorDataset(train_test_result[3], train_test_result[4], train_test_result[5])

# sampler for sampling the data during training
val_sampler = SequentialSampler(val_data)

# dataLoader for validation set
val_dataloader = DataLoader(val_data, sampler = val_sampler, batch_size=args.batch_size)


# Define Model Architecture

# pass the pre-trained BERT to our define architecture
model = BERT_Arch(bert())

# push the model to GPU
model = model.to(device)

# optimizer from hugging face transformers

# define the optimizer
optimizer = AdamW(model.parameters(), lr = 1e-3)

# Find Class Weights
from sklearn.utils.class_weight import compute_class_weight

#compute the class weights
class_wts = compute_class_weight(class_weight = "balanced", classes= np.unique(train_labels), y= train_labels)
print(class_wts)
# convert class weights to tensor
weights= torch.tensor(class_wts, dtype=torch.float)
weights = weights.to(device)

# loss function
cross_entropy  = nn.NLLLoss(weight=weights)

# number of training epochs
epochs = 10

# Fine-Tune BERT
# function to train the model
def train():
    model.train()

    total_loss, total_accuracy = 0, 0

    # empty list to save model predictions
    total_preds = []

    # iterate over batches
    for step, batch in enumerate(train_dataloader):

        # progress update after every 50 batches.
        if step % 50 == 0 and not step == 0:
            print('  Batch {:>5,}  of  {:>5,}.'.format(step, len(train_dataloader)))

        # push the batch to gpu
        batch = [r.to(device) for r in batch]

        sent_id, mask, labels = batch

        # clear previously calculated gradients
        model.zero_grad()

        # get model predictions for the current batch
        preds = model(sent_id, mask)

        # compute the loss between actual and predicted values
        loss = cross_entropy(preds, labels)

        # add on to the total loss
        total_loss = total_loss + loss.item()

        # backward pass to calculate the gradients
        loss.backward()

        # clip the the gradients to 1.0. It helps in preventing the exploding gradient problem
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)

        # update parameters
        optimizer.step()

        # model predictions are stored on GPU. So, push it to CPU
        preds = preds.detach().cpu().numpy()

        # append the model predictions
        total_preds.append(preds)

    # compute the training loss of the epoch
    avg_loss = total_loss / len(train_dataloader)

    # predictions are in the form of (no. of batches, size of batch, no. of classes).
    # reshape the predictions in form of (number of samples, no. of classes)
    total_preds = np.concatenate(total_preds, axis=0)

    # returns the loss and predictions
    return avg_loss, total_preds


# function for evaluating the model
def evaluate():
    print("\nEvaluating...")

    # deactivate dropout layers
    model.eval()

    total_loss, total_accuracy = 0, 0

    # empty list to save the model predictions
    total_preds = []

    # iterate over batches
    for step, batch in enumerate(val_dataloader):

        # Progress update every 50 batches.
        if step % 50 == 0 and not step == 0:
            # Calculate elapsed time in minutes.
            #elapsed = format_time(time.time() - t0)

            # Report progress.
            print('  Batch {:>5,}  of  {:>5,}.'.format(step, len(val_dataloader)))

        # push the batch to gpu
        batch = [t.to(device) for t in batch]

        sent_id, mask, labels = batch

        # deactivate autograd
        with torch.no_grad():

            # model predictions
            preds = model(sent_id, mask)

            # compute the validation loss between actual and predicted values
            loss = cross_entropy(preds, labels)

            total_loss = total_loss + loss.item()

            preds = preds.detach().cpu().numpy()

            total_preds.append(preds)

    # compute the validation loss of the epoch
    avg_loss = total_loss / len(val_dataloader)

    # reshape the predictions in form of (number of samples, no. of classes)
    total_preds = np.concatenate(total_preds, axis=0)

    return avg_loss, total_preds

# Start Model Training
# set initial loss to infinite
best_valid_loss = float('inf')

# empty lists to store training and validation loss of each epoch
train_losses = []
valid_losses = []
import os
path = os.path.join("saved_"+args.model+".pt")
# for each epoch
for epoch in range(epochs):

    print('\n Epoch {:} / {:}'.format(epoch + 1, epochs))

    # train model
    train_loss, _ = train()

    # evaluate model
    valid_loss, _ = evaluate()

    # save the best model
    if valid_loss < best_valid_loss:
        best_valid_loss = valid_loss
        #torch.save(model.state_dict(), 'saved_weights_cased.pt')
        torch.save(model.state_dict(), path)

    # append training and validation loss
    train_losses.append(train_loss)
    valid_losses.append(valid_loss)

    print(f'\nTraining Loss: {train_loss:.3f}')
    print(f'Validation Loss: {valid_loss:.3f}')


# Load Saved Model
#load weights of best model
#bert = AutoModel.from_pretrained(args.model)
# Load the BERT tokenizer
#tokenizer = BertTokenizerFast.from_pretrained(args.model)

#path = 'saved_weights_cased.pt'
model.load_state_dict(torch.load(path))

    # Get Predictions for Test Data
with torch.no_grad():
    preds = model(train_test_result[6].to(device), train_test_result[7].to(device))
    preds = preds.detach().cpu().numpy()

    # model's performance
preds = np.argmax(preds, axis=1)
result = classification_report(train_test_result[8], preds)
    # confusion matrix
pd.crosstab(train_test_result[8], preds)

with open(results_file_path, 'a') as file:
    file.write("Model, Test accuracy\n")
    file.write(f"{args.model}, {result}")
