from ctypes import *
import numpy as np
import scipy.misc as smp
import struct
import tensorflow as tf

def getImgData(plen, mh, mw):
	pix_ptr = cast(getPix(), POINTER(c_char))
	pixList = []
	#print("Width:", mw, "Height:", mh, "Total:", plen)
	for i in range(0, plen, 4):
		#pixList.append([struct.unpack('B', pix_ptr[i])[0], struct.unpack('B', pix_ptr[i+1])[0], struct.unpack('B', pix_ptr[i+2])[0]])
		pixList.append(int((0.3*struct.unpack('B', pix_ptr[i])[0]) + (0.59*struct.unpack('B', pix_ptr[i+1])[0]) + (0.11*struct.unpack('B', pix_ptr[i+2])[0])))
	
	return np.array(pixList).reshape([mw, mh, 1])

def makeConvLayer(pData, channelN, filterN, filterS, poolS, strideN):
    conv_filterS = [filterS[0], filterS[1], channelN, filterN]
    weights = tf.Variable(tf.truncated_normal(conv_filterS, stddev=0.03))
    bias = tf.Variable(tf.truncated_normal([filterN]))
    out_layer = tf.nn.conv2d(pData, weights, [strideN[0], strideN[1], 1, 1], padding='SAME')
    out_layer += bias
    out_layer = tf.nn.relu(out_layer)
    ksize = [1, poolS[0], poolS[1], 1]
    strides = [1, 2, 2, 1]
    out_layer = tf.nn.max_pool(out_layer, ksize=ksize, strides=strides, padding='SAME')

    return out_layer

def runConvNet(plen, mh, mw, lrt):
	pData = getImgData(plen, mh, mw)
	x = tf.placeholder(tf.float32, shape=[4, mw, mh, 1])
	y = tf.placeholder(tf.float32, [8])

	L1 = makeConvLayer(x, 1, 32, [8, 8], [4, 4], [1, 1])
	L2 = makeConvLayer(L1, 32, 64, [4, 4], [3, 3], [1, 1])
	L3 = makeConvLayer(L2, 64, 64, [3, 3], [1, 1], [1, 1])
	nlen = int(150528)

	L3_flat = tf.reshape(L3, [1, nlen])

	weight_d1 = tf.Variable(tf.truncated_normal([nlen, 512], stddev=0.03))
	bias_d1 = tf.Variable(tf.truncated_normal([512], stddev=0.01))
	denseL1 = tf.matmul(L3_flat, weight_d1) + bias_d1
	denseL1 = tf.nn.relu(denseL1)

	weight_out = tf.Variable(tf.truncated_normal([512, 8], stddev=0.03))
	bias_out = tf.Variable(tf.truncated_normal([8], stddev=0.01))
	out_layer = tf.matmul(denseL1, weight_out) + bias_out
	out_layer = tf.nn.relu(out_layer)

	cost = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(labels=y, logits=out_layer))
	trainer = tf.train.AdamOptimizer(lrt).minimize(cost)

	sess = tf.Session()
	init = tf.global_variables_initializer().run(session=sess)

	_, pi = sess.run([trainer, out_layer], feed_dict={y: [0, 0, 0, 0, 0, 0, 1, 0], x: [pData, pData, pData, pData]})
	print(pi[0])


luft_util = CDLL("luft_util.dll")
getPix = luft_util.getPix
getPix.restype = c_ulonglong

ScoreArr = c_int32 * 2
score = ScoreArr(0, 0)

l_rate = .0001

luft_util.init()
pixLen = luft_util.getPLen()
img_h = luft_util.getH()
img_w = luft_util.getW()

runConvNet(pixLen, img_h, img_w, l_rate)

luft_util.closePMem()

