import os
import numpy as np
import tensorflow as tf
from tensorflow.keras.applications import ResNet50V2
from tensorflow.keras.layers import Dense, LayerNormalization, Dropout, Embedding
from tensorflow.keras.models import Model
from PIL import Image as PILImage, UnidentifiedImageError
from io import BytesIO
import requests
import pickle

# Initialize and load models
image_model = ResNet50V2(include_top=False, weights='imagenet')
new_input = image_model.input
hidden_layer = image_model.layers[-1].output
image_features_extract_model = Model(new_input, hidden_layer)

# TensorFlow models and functions
def get_angles(pos, i, d_model):
    angle_rates = 1 / np.power(10000, (2 * (i // 2)) / np.float32(d_model))
    return pos * angle_rates

def positional_encoding_1d(position, d_model):
    angle_rads = get_angles(np.arange(position)[:, np.newaxis],
                            np.arange(d_model)[np.newaxis, :],
                            d_model)

    angle_rads[:, 0::2] = np.sin(angle_rads[:, 0::2])
    angle_rads[:, 1::2] = np.cos(angle_rads[:, 1::2])

    pos_encoding = angle_rads[np.newaxis, ...]

    return tf.cast(pos_encoding, dtype=tf.float32)

def positional_encoding_2d(row, col, d_model):
    assert d_model % 2 == 0
    row_pos = np.repeat(np.arange(row), col)[:, np.newaxis]
    col_pos = np.repeat(np.expand_dims(np.arange(col), 0), row, axis=0).reshape(-1, 1)
    angle_rads_row = get_angles(row_pos, np.arange(d_model // 2)[np.newaxis, :], d_model // 2)
    angle_rads_col = get_angles(col_pos, np.arange(d_model // 2)[np.newaxis, :], d_model // 2)
    angle_rads_row[:, 0::2] = np.sin(angle_rads_row[:, 0::2])
    angle_rads_row[:, 1::2] = np.cos(angle_rads_row[:, 1::2])
    angle_rads_col[:, 0::2] = np.sin(angle_rads_col[:, 0::2])
    angle_rads_col[:, 1::2] = np.cos(angle_rads_col[:, 1::2])
    pos_encoding = np.concatenate([angle_rads_row, angle_rads_col], axis=1)[np.newaxis, ...]

    return tf.cast(pos_encoding, dtype=tf.float32)

def create_padding_mask(seq):
    seq = tf.cast(tf.math.equal(seq, 0), tf.float32)
    return seq[:, tf.newaxis, tf.newaxis, :]

def create_look_ahead_mask(size):
    mask = 1 - tf.linalg.band_part(tf.ones((size, size)), -1, 0)
    return mask

def scaled_dot_product_attention(q, k, v, mask):
    matmul_qk = tf.matmul(q, k, transpose_b=True)
    dk = tf.cast(tf.shape(k)[-1], tf.float32)
    scaled_attention_logits = matmul_qk / tf.math.sqrt(dk)

    if mask is not None:
        scaled_attention_logits += (mask * -1e9)

    attention_weights = tf.nn.softmax(scaled_attention_logits, axis=-1)
    output = tf.matmul(attention_weights, v)

    return output, attention_weights

class MultiHeadAttention(tf.keras.layers.Layer):
    def __init__(self, d_model, num_heads):
        super(MultiHeadAttention, self).__init__()
        self.num_heads = num_heads
        self.d_model = d_model

        assert d_model % self.num_heads == 0

        self.depth = d_model // self.num_heads

        self.wq = tf.keras.layers.Dense(d_model)
        self.wk = tf.keras.layers.Dense(d_model)
        self.wv = tf.keras.layers.Dense(d_model)

        self.dense = tf.keras.layers.Dense(d_model)

    def split_heads(self, x, batch_size):
        x = tf.reshape(x, (batch_size, -1, self.num_heads, self.depth))
        return tf.transpose(x, perm=[0, 2, 1, 3])

    def call(self, v, k, q, mask):
        batch_size = tf.shape(q)[0]

        q = self.wq(q)
        k = self.wk(k)
        v = self.wv(v)

        q = self.split_heads(q, batch_size)
        k = self.split_heads(k, batch_size)
        v = self.split_heads(v, batch_size)

        scaled_attention, attention_weights = scaled_dot_product_attention(q, k, v, mask)
        scaled_attention = tf.transpose(scaled_attention, perm=[0, 2, 1, 3])
        concat_attention = tf.reshape(scaled_attention, (batch_size, -1, self.d_model))

        output = self.dense(concat_attention)

        return output, attention_weights

def point_wise_feed_forward_network(d_model: int, dff: int) -> tf.keras.Sequential:
    return tf.keras.Sequential([
        tf.keras.layers.Dense(dff, activation='relu'),
        tf.keras.layers.Dense(d_model)
    ])

class EncoderLayer(tf.keras.layers.Layer):
    def __init__(self, d_model, num_heads, dff, rate=0.1):
        super(EncoderLayer, self).__init__()

        self.mha = MultiHeadAttention(d_model, num_heads)
        self.ffn = point_wise_feed_forward_network(d_model, dff)

        self.layernorm1 = tf.keras.layers.LayerNormalization(epsilon=1e-6)
        self.layernorm2 = tf.keras.layers.LayerNormalization(epsilon=1e-6)

        self.dropout1 = tf.keras.layers.Dropout(rate)
        self.dropout2 = tf.keras.layers.Dropout(rate)

    def call(self, x, training, mask=None):
        attn_output, _ = self.mha(v=x, k=x, q=x, mask=mask)
        attn_output = self.dropout1(attn_output, training=training)
        out1 = self.layernorm1(x + attn_output)

        ffn_output = self.ffn(out1)
        ffn_output = self.dropout2(ffn_output, training=training)
        out2 = self.layernorm2(out1 + ffn_output)

        return out2

class Encoder(tf.keras.layers.Layer):
    def __init__(self, num_layers: int, d_model: int, num_heads: int, dff: int,
                 row_size: int, col_size: int, rate: float = 0.1):
        super(Encoder, self).__init__()

        self.d_model = d_model
        self.num_layers = num_layers

        self.embedding = tf.keras.layers.Dense(self.d_model, activation='relu')
        self.pos_encoding = positional_encoding_2d(row_size, col_size, self.d_model)

        self.enc_layers = [EncoderLayer(d_model, num_heads, dff, rate) for _ in range(self.num_layers)]
        self.dropout = tf.keras.layers.Dropout(rate)

    def call(self, x: tf.Tensor, training: bool, mask: tf.Tensor = None):
        seq_len = tf.shape(x)[1]

        x = self.embedding(x)
        x += self.pos_encoding[:, :seq_len, :]
        x = self.dropout(x, training=training)

        for i in range(self.num_layers):
            x = self.enc_layers[i](x, training=training, mask=mask)

        return x

class DecoderLayer(tf.keras.layers.Layer):
    def __init__(self, d_model, num_heads, dff, rate=0.1):
        super(DecoderLayer, self).__init__()

        self.mha1 = MultiHeadAttention(d_model, num_heads)
        self.mha2 = MultiHeadAttention(d_model, num_heads)

        self.ffn = point_wise_feed_forward_network(d_model, dff)

        self.layernorm1 = tf.keras.layers.LayerNormalization(epsilon=1e-6)
        self.layernorm2 = tf.keras.layers.LayerNormalization(epsilon=1e-6)
        self.layernorm3 = tf.keras.layers.LayerNormalization(epsilon=1e-6)

        self.dropout1 = tf.keras.layers.Dropout(rate)
        self.dropout2 = tf.keras.layers.Dropout(rate)
        self.dropout3 = tf.keras.layers.Dropout(rate)

    def call(self, x, enc_output, training, look_ahead_mask=None, padding_mask=None):
        attn1, attn_weights_block1 = self.mha1(v=x, k=x, q=x, mask=look_ahead_mask)
        attn1 = self.dropout1(attn1, training=training)
        out1 = self.layernorm1(attn1 + x)

        attn2, attn_weights_block2 = self.mha2(v=enc_output, k=enc_output, q=out1, mask=padding_mask)
        attn2 = self.dropout2(attn2, training=training)
        out2 = self.layernorm2(attn2 + out1)

        ffn_output = self.ffn(out2)
        ffn_output = self.dropout3(ffn_output, training=training)
        out3 = self.layernorm3(ffn_output + out2)

        return out3, attn_weights_block1, attn_weights_block2

class Decoder(tf.keras.layers.Layer):
    def __init__(self, num_layers, d_model, num_heads, dff, target_vocab_size, maximum_position_encoding, rate=0.1):
        super(Decoder, self).__init__()

        self.d_model = d_model
        self.num_layers = num_layers

        self.embedding = tf.keras.layers.Embedding(target_vocab_size, d_model)
        self.pos_encoding = positional_encoding_1d(maximum_position_encoding, d_model)

        self.dec_layers = [DecoderLayer(d_model, num_heads, dff, rate) for _ in range(num_layers)]
        self.dropout = tf.keras.layers.Dropout(rate)

    def call(self, x, enc_output, training, look_ahead_mask=None, padding_mask=None):
        seq_len = tf.shape(x)[1]
        attention_weights = {}

        x = self.embedding(x)
        x *= tf.math.sqrt(tf.cast(self.d_model, tf.float32))
        x += self.pos_encoding[:, :seq_len, :]

        x = self.dropout(x, training=training)

        for i in range(self.num_layers):
            x, block1, block2 = self.dec_layers[i](x, enc_output, training=training, look_ahead_mask=look_ahead_mask, padding_mask=padding_mask)

            attention_weights[f'decoder_layer{i+1}_block1'] = block1
            attention_weights[f'decoder_layer{i+1}_block2'] = block2

        return x, attention_weights

class Transformer(tf.keras.Model):
    def __init__(self, num_layers: int, d_model: int, num_heads: int, dff: int,
                 row_size: int, col_size: int, target_vocab_size: int,
                 max_pos_encoding: int, rate: float = 0.1):
        super(Transformer, self).__init__()

        self.encoder = Encoder(num_layers, d_model, num_heads, dff, row_size, col_size, rate)
        self.decoder = Decoder(num_layers, d_model, num_heads, dff, target_vocab_size, max_pos_encoding, rate)
        self.final_layer = tf.keras.layers.Dense(target_vocab_size)

    def call(self, inp: tf.Tensor, tar: tf.Tensor, training: bool,
             look_ahead_mask: tf.Tensor = None, dec_padding_mask: tf.Tensor = None,
             enc_padding_mask: tf.Tensor = None):
        enc_output = self.encoder(inp, training=training, mask=enc_padding_mask)

        dec_output, attention_weights = self.decoder(
            x=tar, enc_output=enc_output, training=training, look_ahead_mask=look_ahead_mask, padding_mask=dec_padding_mask)

        final_output = self.final_layer(dec_output)

        return final_output, attention_weights

# Load the saved tokenizer
tokenizer = pickle.load(open('./assets/tokenizer.pickle', 'rb'))

# Define model parameters
top_k = 1732
num_layer = 2
d_model = 128
dff = 2048
num_heads = 2
row_size = 8
col_size = 8
target_vocab_size = top_k + 1
dropout_rate = 0.1

# Initialize the Transformer model
transformer = Transformer(
    num_layer,
    d_model,
    num_heads,
    dff,
    row_size,
    col_size,
    target_vocab_size,
    max_pos_encoding=target_vocab_size,
    rate=dropout_rate
)

# Dummy call to create the model variables
dummy_input = tf.random.uniform((1, row_size * col_size, 2048))
dummy_target = tf.random.uniform((1, 1), maxval=target_vocab_size, dtype=tf.int32)
_ = transformer(dummy_input, dummy_target, training=False)

# Load pre-trained weights
transformer.load_weights('./assets/model.weights.h5')

# Valid image formats
VALID_IMAGE_FORMATS = {"image/jpeg", "image/png", "image/webp", "jpg", "jpeg", "png", "webp"}

def load_image_from_file(file):
    try:
        img = PILImage.open(BytesIO(file.read()))
        if img.format.lower() not in VALID_IMAGE_FORMATS:
            raise ValueError("Invalid image format")
        
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        img = img.resize((224, 224))
        img = np.array(img)
        img = tf.keras.applications.resnet_v2.preprocess_input(img)
        img = np.expand_dims(img, axis=0)
        return img
    except UnidentifiedImageError:
        raise ValueError("Invalid image file")

def create_masks_decoder(tar: tf.Tensor) -> tf.Tensor:
    look_ahead_mask = create_look_ahead_mask(tf.shape(tar)[1])
    dec_target_padding_mask = create_padding_mask(tar)
    combined_mask = tf.maximum(dec_target_padding_mask, look_ahead_mask)
    return combined_mask

def beam_search_decoder(predictions, beam_width):
    sequences = [[list(), 1.0]]
    for row in predictions:
        all_candidates = list()
        for i in range(len(sequences)):
            seq, score = sequences[i]
            for j in range(len(row)):
                candidate = [seq + [j], score * -np.log(row[j])]
                all_candidates.append(candidate)
        ordered = sorted(all_candidates, key=lambda tup: tup[1])
        sequences = ordered[:beam_width]
    return sequences

def evaluate_beam_search(image_tensor, beam_width=3):
    img_tensor_val = image_features_extract_model(image_tensor)
    img_tensor_val = tf.reshape(img_tensor_val, (img_tensor_val.shape[0], -1, img_tensor_val.shape[3]))

    start_token = tokenizer.word_index['<start>']
    end_token = tokenizer.word_index['<end>']

    decoder_input = [start_token]
    output = tf.expand_dims(decoder_input, 0)

    result = []

    for i in range(100):
        dec_mask = create_masks_decoder(output)
        predictions, attention_weights = transformer(img_tensor_val, output, training=False, look_ahead_mask=dec_mask)
        predictions = tf.nn.softmax(predictions, axis=-1).numpy()

        sequences = beam_search_decoder(predictions[:, -1, :], beam_width)
        predicted_id = sequences[0][0][-1]

        if predicted_id == end_token:
            return result, tf.squeeze(output, axis=0), attention_weights

        result.append(tokenizer.index_word[predicted_id])
        output = tf.concat([output, tf.expand_dims([predicted_id], 0)], axis=-1)

    return result, tf.squeeze(output, axis=0), attention_weights

def correct_caption(caption: str) -> str:
    url = "https://api.nyxs.pw/ai/gpt4"
    query_params = {"text": f"Perbaiki teks berikut dan tambahkan tanda baca yang sesuai: \"{caption}\""}
    response = requests.get(url, params=query_params)
    if response.status_code == 200:
        corrected_caption = response.json().get("result", caption)
        return corrected_caption.strip('"')
    else:
        raise ValueError("Failed to correct caption")