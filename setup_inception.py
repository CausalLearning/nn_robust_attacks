## Modified by Nicholas Carlini to match model structure for attack code.
## Original copyright license follows.


# Copyright 2015 The TensorFlow Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================

"""Simple image classification with Inception.

Run image classification with Inception trained on ImageNet 2012 Challenge data
set.

This program creates a graph from a saved GraphDef protocol buffer,
and runs inference on an input JPEG image. It outputs human readable
strings of the top 5 predictions along with their probabilities.

Change the --image_file argument to any jpg image to compute a
classification of that image.

Please see the tutorial and website for a detailed description of how
to use this script to perform image recognition.

https://tensorflow.org/tutorials/image_recognition/
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os.path
import re
import sys
import tarfile
import scipy.misc

import numpy as np
from six.moves import urllib
import tensorflow as tf

FLAGS = tf.app.flags.FLAGS

# classify_image_graph_def.pb:
#   Binary representation of the GraphDef protocol buffer.
# imagenet_synset_to_human_label_map.txt:
#   Map from synset ID to a human readable string.
# imagenet_2012_challenge_label_map_proto.pbtxt:
#   Text representation of a protocol buffer mapping a label to synset ID.
tf.app.flags.DEFINE_string(
		'model_dir', 'tmp/imagenet',
		"""Path to classify_image_graph_def.pb, """
		"""imagenet_synset_to_human_label_map.txt, and """
		"""imagenet_2012_challenge_label_map_proto.pbtxt.""")
tf.app.flags.DEFINE_string('image_file', '',
													 """Absolute path to image file.""")
tf.app.flags.DEFINE_integer('num_top_predictions', 5,
														"""Display this many predictions.""")

# pylint: disable=line-too-long
DATA_URL = 'http://download.tensorflow.org/models/image/imagenet/inception-2015-12-05.tgz'
# pylint: enable=line-too-long


class NodeLookup(object):
	"""Converts integer node ID's to human readable labels."""

	def __init__(self,
							 label_lookup_path=None,
							 uid_lookup_path=None):
		if not label_lookup_path:
			label_lookup_path = os.path.join(
					FLAGS.model_dir, 'imagenet_2012_challenge_label_map_proto.pbtxt')
		if not uid_lookup_path:
			uid_lookup_path = os.path.join(
					FLAGS.model_dir, 'imagenet_synset_to_human_label_map.txt')
		self.node_lookup = self.load(label_lookup_path, uid_lookup_path)

	def load(self, label_lookup_path, uid_lookup_path):
		"""Loads a human readable English name for each softmax node.

		Args:
			label_lookup_path: string UID to integer node ID.
			uid_lookup_path: string UID to human-readable string.

		Returns:
			dict from integer node ID to human-readable string.
		"""
		if not tf.gfile.Exists(uid_lookup_path):
			tf.logging.fatal('File does not exist %s', uid_lookup_path)
		if not tf.gfile.Exists(label_lookup_path):
			tf.logging.fatal('File does not exist %s', label_lookup_path)

		# Loads mapping from string UID to human-readable string
		proto_as_ascii_lines = tf.gfile.GFile(uid_lookup_path).readlines()
		uid_to_human = {}
		p = re.compile(r'[n\d]*[ \S,]*')
		for line in proto_as_ascii_lines:
			parsed_items = p.findall(line)
			uid = parsed_items[0]
			human_string = parsed_items[2]
			uid_to_human[uid] = human_string

		# Loads mapping from string UID to integer node ID.
		node_id_to_uid = {}
		proto_as_ascii = tf.gfile.GFile(label_lookup_path).readlines()
		for line in proto_as_ascii:
			if line.startswith('  target_class:'):
				target_class = int(line.split(': ')[1])
			if line.startswith('  target_class_string:'):
				target_class_string = line.split(': ')[1]
				node_id_to_uid[target_class] = target_class_string[1:-2]

		# Loads the final mapping of integer node ID to human-readable string
		node_id_to_name = {}
		for key, val in node_id_to_uid.items():
			if val not in uid_to_human:
				tf.logging.fatal('Failed to locate: %s', val)
			name = uid_to_human[val]
			node_id_to_name[key] = name

		return node_id_to_name

	def id_to_string(self, node_id):
		if node_id not in self.node_lookup:
			return ''
		return self.node_lookup[node_id]


def create_graph():
	"""Creates a graph from saved GraphDef file and returns a saver."""
	# Creates graph from saved graph_def.pb.
	with tf.gfile.FastGFile(os.path.join(
			FLAGS.model_dir, 'classify_image_graph_def.pb'), 'rb') as f:
		graph_def = tf.GraphDef()
		graph_def.ParseFromString(f.read())
		#for line in repr(graph_def).split("\n"):
		#  if "tensor_content" not in line:
		#    print(line)
		_ = tf.import_graph_def(graph_def, name='')


def run_inference_on_image(image):
	"""Runs inference on an image.

	Args:
		image: Image file name.

	Returns:
		Nothing
	"""
	if not tf.gfile.Exists(image):
		tf.logging.fatal('File does not exist %s', image)
	image_data = tf.gfile.FastGFile(image, 'rb').read()

	# Creates graph from saved GraphDef.
	create_graph()

	with tf.Session() as sess:
		# Some useful tensors:
		# 'softmax:0': A tensor containing the normalized prediction across
		#   1000 labels.
		# 'pool_3:0': A tensor containing the next-to-last layer containing 2048
		#   float description of the image.
		# 'DecodeJpeg/contents:0': A tensor containing a string providing JPEG
		#   encoding of the image.
		# Runs the softmax tensor by feeding the image_data as input to the graph.
		#softmax_tensor = sess.graph.get_tensor_by_name('softmax:0')
		img = tf.placeholder(tf.uint8, (299,299,3))
		softmax_tensor = tf.import_graph_def(
						sess.graph.as_graph_def(),
						input_map={'DecodeJpeg:0': tf.reshape(img,((299,299,3)))},
						return_elements=['softmax/logits:0'])

		dat = scipy.misc.imresize(scipy.misc.imread(image),(299,299))
		predictions = sess.run(softmax_tensor,
													 {img: dat})

		predictions = np.squeeze(predictions)

		# Creates node ID --> English string lookup.
		node_lookup = NodeLookup()

		top_k = predictions.argsort()#[-FLAGS.num_top_predictions:][::-1]
		for node_id in top_k:
			print('id',node_id)
			human_string = node_lookup.id_to_string(node_id)
			score = predictions[node_id]
			print('%s (score = %.5f)' % (human_string, score))

CREATED_GRAPH = False
class InceptionModel:
	image_size = 299
	num_labels = 1008
	num_channels = 3
	def __init__(self, sess):
		global CREATED_GRAPH
		self.sess = sess
		if not CREATED_GRAPH:
			create_graph()
			CREATED_GRAPH = True

	def predict(self, img):
		scaled = (0.5+tf.reshape(img,((299,299,3))))*255
		softmax_tensor = tf.import_graph_def(
			self.sess.graph.as_graph_def(),
			input_map={'Cast:0': scaled},
			return_elements=['softmax/logits:0'])
		return softmax_tensor[0]
	

def maybe_download_and_extract():
	"""Download and extract model tar file."""
	dest_directory = FLAGS.model_dir
	if not os.path.exists(dest_directory):
		os.makedirs(dest_directory)
	filename = DATA_URL.split('/')[-1]
	filepath = os.path.join(dest_directory, filename)
	if not os.path.exists(filepath):
		def _progress(count, block_size, total_size):
			sys.stdout.write('\r>> Downloading %s %.1f%%' % (
					filename, float(count * block_size) / float(total_size) * 100.0))
			sys.stdout.flush()
		filepath, _ = urllib.request.urlretrieve(DATA_URL, filepath, _progress)
		print()
		statinfo = os.stat(filepath)
		print('Succesfully downloaded', filename, statinfo.st_size, 'bytes.')
	tarfile.open(filepath, 'r:gz').extractall(dest_directory)


def main(_):
	maybe_download_and_extract()
	image = (FLAGS.image_file if FLAGS.image_file else
					 os.path.join(FLAGS.model_dir, 'cropped_panda.jpg'))
	run_inference_on_image(image)


def readimg(ff):
	f = "../imagenetdata/imgs/"+ff
	img = np.array(scipy.misc.imresize(scipy.misc.imread(f),(299,299)),dtype=np.float32)/255-.5
	if img.shape != (299, 299, 3):
		return None
	return [img, int(ff.split(".")[0])]

class ImageNet:
	def __init__(self):
		from multiprocessing import Pool
		pool = Pool(8)
		r = pool.map(readimg, os.listdir("../imagenetdata/imgs/")[:200])
		r = [x for x in r if x != None]
		test_data, test_labels = zip(*r)
		self.test_data = np.array(test_data)
		self.test_labels = np.zeros((len(test_labels), 1008))
		self.test_labels[np.arange(len(test_labels)), test_labels] = 1

	


if __name__ == '__main__':
	tf.app.run()
