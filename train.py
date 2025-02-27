"""Train the model"""
#train.py to change from train to evaluate

import argparse
import logging
import os

import tensorflow as tf

from model.utils import Params
from model.utils import set_logger
from model.training import train_and_evaluate
from model.input_fn import input_fn
from model.input_fn import load_dataset_from_csv
from model.model_fn import model_fn


parser = argparse.ArgumentParser()
parser.add_argument('--model_dir', default='experiments',
                    help="Directory containing params.json")
parser.add_argument('--data_dir', default='data', help="Directory containing the dataset")
parser.add_argument('--restore_dir', default=None,
                    help="Optional, directory containing weights to reload before training")


if __name__ == '__main__':
    # Set the random seed for the whole graph for reproductible experiments
    tf.set_random_seed(42)

    # Load the parameters from the experiment params.json file in model_dir
    args = parser.parse_args()
    json_path = os.path.join(args.model_dir, 'params.json')
    assert os.path.isfile(json_path), "No json configuration file found at {}".format(json_path)
    params = Params(json_path)

    # Load the parameters from the dataset, that gives the size etc. into params
    json_path = os.path.join(args.data_dir, 'dataset_params.json')
    assert os.path.isfile(json_path), "No json file found at {}, run build_vocab.py".format(json_path)
    params.update(json_path)
    # num_oov_buckets = params.num_oov_buckets # number of buckets for unknown words

    # Check that we are not overwriting some previous experiment
    # Comment these lines if you are developing your model and don't care about overwritting
    # model_dir_has_best_weights = os.path.isdir(os.path.join(args.model_dir, "best_weights"))
    # overwritting = model_dir_has_best_weights and args.restore_dir is None
    # assert not overwritting, "Weights found in model_dir, aborting to avoid overwrite"

    # Set the logger
    set_logger(os.path.join(args.model_dir, 'train.log'))

    # Get paths for vocabularies and dataset
    # path_words = os.path.join(args.data_dir, 'words.txt')
    # path_tags = os.path.join(args.data_dir, 'tags.txt')
    # path_train_sentences = os.path.join(args.data_dir, 'train/sentences.txt')
    # path_train_labels = os.path.join(args.data_dir, 'train/labels.txt')
    # path_eval_sentences = os.path.join(args.data_dir, 'dev/sentences.txt')
    # path_eval_labels = os.path.join(args.data_dir, 'dev/labels.txt')

    # Load Vocabularies
    # words = tf.contrib.lookup.index_table_from_file(path_words, num_oov_buckets=num_oov_buckets)
    # tags = tf.contrib.lookup.index_table_from_file(path_tags)

    # Create the input data pipeline
    logging.info("Creating the datasets...")
    train_x = load_dataset_from_csv(filenames = ["data/train/data-in.csv"],params = params)
    train_y = load_dataset_from_csv(filenames = ["data/train/data-out.csv"],params = params)
    eval_x = load_dataset_from_csv(filenames = ["data/test/data-in.csv"],params = params)
    eval_y = load_dataset_from_csv(filenames = ["data/test/data-out.csv"],params = params)


    # Specify other parameters for the dataset and the model
    params.eval_size = params.dev_size

    params.buffer_size = 3400#params.train_size # buffer size for shuffling
    params.restore_dir= args.restore_dir#"experiments/last_weights"#"experiments/best_weights"#"experiments/last_weights"#None#args.restore_dir#"experiments/best_weights"#None#

    # Create the two iterators over the two datasets
    train_inputs = input_fn('train', train_x,train_y, params)

    eval_inputs = input_fn('eval', eval_x,eval_y, params)
    logging.info("- done.")

    # Define the models (2 different set of nodes that share weights for train and eval)
    logging.info("Creating the model...")
    train_model_spec = model_fn('train', train_inputs, params)
    eval_model_spec = model_fn('eval', eval_inputs, params, reuse=True)
    logging.info("- done.")

    # Train the model
    logging.info("Starting training for {} epoch(s)".format(params.num_epochs))
    # train_and_evaluate(train_model_spec, eval_model_spec, args.model_dir, params, args.restore_dir)
    train_and_evaluate(train_model_spec, eval_model_spec, args.model_dir, params, params.restore_dir)
