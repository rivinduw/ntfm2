"""Tensorflow utility functions for evaluation"""

import logging
import os
import csv

from tqdm import trange
import tensorflow as tf

import numpy as np

from model.utils import save_dict_to_json


def evaluate_sess(sess, model_spec, num_steps, writer=None, params=None):
    """Train the model on `num_steps` batches.

    Args:
        sess: (tf.Session) current session
        model_spec: (dict) contains the graph operations or nodes needed for training
        num_steps: (int) train for this number of batches
        writer: (tf.summary.FileWriter) writer for summaries. Is None if we don't log anything
        params: (Params) hyperparameters
    """
    update_metrics = model_spec['update_metrics']
    eval_metrics = model_spec['metrics']
    global_step = tf.train.get_global_step()

    # Load the evaluation dataset into the pipeline and initialize the metrics init op
    sess.run(model_spec['iterator_init_op'])
    sess.run(model_spec['metrics_init_op'])

    # compute metrics over the dataset
    for _ in range(num_steps):
        sess.run(update_metrics)
        # predicted_outputs,labels,input_batch = sess.run([model_spec['predictions'],model_spec['labels'],model_spec['input_batch']])
        # with open('preds.csv','a+') as fd:
        #     csvwriter = csv.writer(fd)
        #     csvwriter.writerows(predicted_outputs[:,180,:])


    # Get the values of the metrics
    metrics_values = {k: v[0] for k, v in eval_metrics.items()}
    metrics_val = sess.run(metrics_values)
    metrics_string = " ; ".join("{}: {:05.3f}".format(k, v) for k, v in metrics_val.items())
    logging.info("- Eval metrics: " + metrics_string)

    # DELETE DEBUGGING CODE write out to csv the inputs and outputs/predictions
    predicted_outputs,labels,input_batch = sess.run([model_spec['predictions'],model_spec['labels'],model_spec['input_batch']])
    #params.batch_size,params.window_size,params.num_cols
    import pandas as pd
    # pd.DataFrame(predicted_outputs[:,180,:]).to_csv('predicted_outputs_180.csv')
    # pd.DataFrame(labels[:,180,:]).to_csv('labels_180.csv')
    # pd.DataFrame(input_batch[:,180,:]).to_csv('input_batch_180.csv')

    print(predicted_outputs.shape)
    print(labels.shape)
    print(input_batch.shape)
    predicted_outputs = predicted_outputs.reshape((params.batch_size,params.window_size,params.num_segs*5))
    labels = labels.reshape((params.batch_size,params.window_size,params.num_segs*5))
    input_batch = input_batch.reshape((params.batch_size,params.window_size,params.num_segs*5))

    def rolling_sum(a, n=30) :
        ret = np.cumsum(a, axis=0, dtype=float)
        ret[n:, :] = ret[n:, :] - ret[:-n, :]
        #ret[n:, ::2] = ret[n:, ::2] - ret[:-n, ::2]
        # ret[n:,1::2] = np.divide(ret[n:,1::2],n)##even columns are occupancy and shoud be averaged instead of summed
        return ret[n - 1:,:]
    def div0( a, b ):
        with np.errstate(divide='ignore', invalid='ignore'):
            a = a.astype(float)
            b = b.astype(float)
            sel = np.bitwise_not(np.isclose(b, 0))
            c = np.true_divide( a[sel], b[sel] )
            c[ ~ np.isfinite( c )] = 0  # -inf inf NaN
        return c
    def regAccuracy(ground_truth, predictions):
        mape = np.mean(np.ma.fix_invalid(np.abs(div0((ground_truth - predictions), ground_truth)),fill_value=0))
        return 1 - mape
    mean_acc = []
    for ii in range(params.batch_size):
        pred_vs = np.array(predicted_outputs[ii,:,:])*30.0
        act_vs = np.array(labels[ii,:,:])*30.0
        # act_mask = act_vs>0.01
        pred_sum = rolling_sum(pred_vs)
        act_sum = rolling_sum(act_vs)
        accu = regAccuracy(act_sum, pred_sum)
        mean_acc.append(accu)
    print("5min approx accuracy: ",np.mean(np.array(mean_acc)))
    pd.DataFrame(np.array(mean_acc)).to_csv('meanAcc.csv')
    pd.DataFrame(predicted_outputs[0,:,:]).to_csv('predicted_outputs.csv')
    pd.DataFrame(labels[0,:,:]).to_csv('labels.csv')
    pd.DataFrame(input_batch[0,:,:]).to_csv('input_batch.csv')


    # Add summaries manually to writer at global_step_val
    if writer is not None:
        global_step_val = sess.run(global_step)
        for tag, val in metrics_val.items():
            summ = tf.Summary(value=[tf.Summary.Value(tag=tag, simple_value=val)])
            writer.add_summary(summ, global_step_val)

    return metrics_val


def evaluate(model_spec, model_dir, params, restore_from):
    """Evaluate the model

    Args:
        model_spec: (dict) contains the graph operations or nodes needed for evaluation
        model_dir: (string) directory containing config, weights and log
        params: (Params) contains hyperparameters of the model.
                Must define: num_epochs, train_size, batch_size, eval_size, save_summary_steps
        restore_from: (string) directory or file containing weights to restore the graph
    """
    # Initialize tf.Saver
    saver = tf.train.Saver()

    with tf.Session() as sess:
        # Initialize the lookup table
        sess.run(model_spec['variable_init_op'])

        # Reload weights from the weights subdirectory
        save_path = os.path.join(model_dir, restore_from)
        if os.path.isdir(save_path):
            save_path = tf.train.latest_checkpoint(save_path)
        saver.restore(sess, save_path)

        # Evaluate
        num_steps = (params.eval_size + params.batch_size - 1) // params.batch_size
        metrics = evaluate_sess(sess, model_spec, num_steps)
        metrics_name = '_'.join(restore_from.split('/'))
        save_path = os.path.join(model_dir, "metrics_test_{}.json".format(metrics_name))
        save_dict_to_json(metrics, save_path)
