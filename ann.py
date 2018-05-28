#!/usr/bin/env python
from __future__ import print_function

import os
import sys
import traceback

import numpy as np
import pandas as pd

from keras.layers import Dropout, Dense
from keras.wrappers.scikit_learn import KerasClassifier
from keras.models import Sequential

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import GridSearchCV


# These are the paths to where SageMaker mounts interesting things in your container.
prefix = '/opt/ml/'

input_path = prefix + 'input/data/training/churn.csv'
output_path = os.path.join(prefix, 'output')
model_path = os.path.join(prefix, 'model')

# This algorithm has a single channel of input data called 'training'. Since we run in
# File mode, the input files are copied to the directory specified here.
channel_name = 'training'
training_path = os.path.join(input_path, channel_name)


# Process and prepare the data
def data_process(raw_data):
    train_data = raw_data
    for col in train_data.columns:
        if col not in ['user_id', 'domain_name']:
            col_mean = np.nanmean(train_data[col], axis=0)
            train_data[col].fillna(col_mean, inplace=True)

    # Replace with average age
    X = train_data.iloc[:, 1:17].values
    y = train_data.iloc[:, 17].values

    # Encoding categorical variables
    labelencoder_X_1 = LabelEncoder()
    X[:, 15] = labelencoder_X_1.fit_transform(X[:, 15])

    # Splitting the dataset into the Training set and Test set
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.25,
        random_state=0)

    # Feature Scaling
    sc = StandardScaler()
    X_train = sc.fit_transform(X_train)
    X_test = sc.fit_transform(X_test)

    return X_train, X_test, y_train, y_test


# Building the ANN
def build_classifier(optimizer):
    # Initialize ANN
    classifier = Sequential()

    # First hidden layer with 10% dropout
    classifier.add(Dense(
        activation="relu",
        input_dim=16,
        units=8,
        kernel_initializer="uniform"))
    classifier.add(Dropout(rate=0.1))

    # The second hidden layer with 10% dropout
    classifier.add(Dense(
        activation="relu",
        units=8,
        kernel_initializer="uniform"))
    classifier.add(Dropout(rate=0.1))

    # Adding the output layer
    classifier.add(Dense(
        activation="sigmoid",
        units=1,
        kernel_initializer="uniform"))

    # Compiling the ANN
    classifier.compile(
        optimizer=optimizer, # efficient SGD
        loss='binary_crossentropy',
        metrics=['accuracy']
    )

    return classifier


def generate_model(X_train, y_train):
    # Build classifier using grid search
    classifier = KerasClassifier(build_fn=build_classifier)

    # Create a dict of hyperparameters to optimize
    parameters = {
        # Tune batch size, epoch, optimizer
        'batch_size': [25, 32],
        'nb_epoch': [100, 500],
        'optimizer': ['adam', 'rmsprop']
    }

    # Implement GridSearch
    grid_search = GridSearchCV(
        estimator=classifier,
        param_grid=parameters,
        scoring='accuracy',
        cv=10
    )

    # Fit gridsearch to training set
    optimized_classifier = grid_search.fit(
        X_train,
        y_train
    )

    return optimized_classifier


def train():
    print('Starting the training.')
    try:
        raw_data = pd.read_csv(input_path)
        X_train, X_test, y_train, y_test = data_process(raw_data)
        optimized_classifier = generate_model(X_train, y_train)
        optimized_classifier.save(os.path.join(model_path, 'ann.hd5'))
        print('Training complete.')
    except Exception as e:
        # Write out an error file. This will be returned as the failureReason in the
        # DescribeTrainingJob result.
        trc = traceback.format_exc()
        with open(os.path.join(output_path, 'failure'), 'w') as s:
            s.write('Exception during training: ' + str(e) + '\n' + trc)
        # Printing this causes the exception to be in the training job logs, as well.
        print('Exception during training: ' + str(e) + '\n' + trc, file=sys.stderr)
        # A non-zero exit code causes the training job to be marked as Failed.
        sys.exit(255)

if __name__ == '__main__':
    train()

    # A zero exit code causes the job to be marked a Succeeded.
    sys.exit(0)
