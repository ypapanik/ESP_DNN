from __future__ import absolute_import

from keras import Model
import keras.backend as K
from keras.layers import Dense, Input, Activation, SpatialDropout1D
from keras.optimizers import Adam
from keras.models import load_model
import tensorflow as tf

from esp_dnn.graph_conv import GraphConv


def sum_squared_error_nan(y_true, y_pred):
    return K.sum(tf.compat.v1.where(tf.math.is_nan(y_true), K.zeros_like(y_pred),
                          K.square(y_pred - y_true)), axis=-1)


def sum_absolute_error_nan(y_true, y_pred):
    # this sums esp values for all features in an atom and
    # finally the sum of error is divided by all atoms (including the dummy
    # atoms added for padding (with all nan values). However, this should be
    # alright for minimization purpose.
    return K.sum(tf.compat.v1.where(tf.math.is_nan(y_true), K.zeros_like(y_pred),
                          K.abs(y_pred - y_true)), axis=-1)


def mean_absolute_error_nans(y_true, y_pred):
    y_total = tf.cast(tf.reduce_sum(
        input_tensor=tf.cast(~tf.math.is_nan(y_true), tf.int32)), tf.float32)
    y_sum_err = tf.reduce_sum(
        input_tensor=tf.compat.v1.where(tf.math.is_nan(y_true), tf.zeros_like(y_pred), K.abs(y_pred - y_true)))
    error = tf.cond(pred=y_total < 0.1, true_fn=lambda: tf.constant(0.0),
                    false_fn=lambda: tf.divide(y_sum_err, y_total))
    return error


SPACE = dict(activation="relu",
             width=120,
             dropout_p=None,
             neigh_wts="single",
             n_conv_layers=2,
             lr=0.0025,
             decay=0.00005)


def build_model(n_features_per_atom, n_ys_per_atom, space=SPACE):
    # variable number of atoms
    A = X = Input(name="X", shape=(None, n_features_per_atom))
    # variable atom connectivity matrix
    D = Input(name="D", shape=(None, None))

    activation = space["activation"]
    width = space["width"]
    dropout_p = space["dropout_p"]
    layer_i = 1

    for _ in range(2):
        A = Dense(width, name="dense_%d" % layer_i, activation=activation)(A)
        A = A if dropout_p is None else SpatialDropout1D(
            dropout_p, name="dropout_%d" % layer_i)(A)
        layer_i += 1

    neigh_wts = space["neigh_wts"]
    for _ in range(space["n_conv_layers"]):
        A = GraphConv(width, name="conv_%d" % layer_i,
                      activation=activation, conv_wts=neigh_wts)([A, D])
        A = A if dropout_p is None else SpatialDropout1D(
            dropout_p, name="dropout_%d" % layer_i)(A)
        layer_i += 1

    for _ in range(2):
        A = Dense(width, name="dense_%d" % layer_i, activation=activation)(A)
        A = A if dropout_p is None else SpatialDropout1D(
            dropout_p, name="dropout_%d" % layer_i)(A)
        layer_i += 1

    A = Dense(n_ys_per_atom, name="dense_last")(A)
    output = Activation(activation="linear", name="output")(A)
    model = Model(inputs=[X, D], outputs=[output])
    model.compile(optimizer=Adam(
        lr=space["lr"], decay=space["decay"]), loss=mean_absolute_error_nans)
    return model


def custom_load_model(model_file):
    return load_model(model_file, custom_objects={
        "mean_absolute_error_nans": mean_absolute_error_nans,
        "GraphConv": GraphConv})


def save_model(model, output_file, weights_only=False):
    ":type model: Model"
    if weights_only:
        model.save_weights(output_file)
    else:
        model.save(output_file, overwrite=True, include_optimizer=True)


def load_weights(model, wts_file):
    ":type model: Model"
    model.load_weights(wts_file)

