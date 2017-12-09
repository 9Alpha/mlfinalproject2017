from ctypes import *
import numpy as np #I'll refer to numpy as np and tensorflow as tf
import struct
import tensorflow as tf
import h5py
import os
import random
import time

SHRINK = 2 #how much to shrink the image cap
DEAD_VAL = 81 #screen color when dead
IS_DEAD = False #if AI is dead

hdinit = False
makeDTable = True #IMPORTANT whether or not to create new d_table

dtFull = False

DLEN = 500000 #d_table len, Maxlen=500000, don't go above this
DSPOT = 0 #spot to replace when adding event to d_table

ScoreArr = c_int32 * 2
SCORE = ScoreArr(0, 0) #ctypes arr for score and mult variables

l_rate = .00005 #learning rate

doRMove = .01

keyCode = ["FIRE  ON", "Left  ON", "Up  ON", "Right  ON", "FIRE Off", "Left Off", "Up Off", "Right Off"]

def getImgData(plen, nw, nh, plist, pspot): #gets pixel data from luft_util
	global IS_DEAD
	pix_ptr = cast(getPix(SHRINK), POINTER(c_char)) #actual method call

	for i in range(nh*nw): #unpack each pixel and add it to np arr
		plist[i][pspot] = struct.unpack('B', pix_ptr[i])[0]


	IS_DEAD = True
	for i in plist[30000:30050][pspot]: #check if screen is dead screen
		if i != DEAD_VAL:
			IS_DEAD = False



def getShortList(llen): #uses a resevoir picker to get llen items from the d_table
	slist = []
	for i in range(DSPOT):
		if i < llen:
			slist.append(i)
		elif random.random() < llen/(i+1):
			slist[random.randint(0, len(slist)-1)] = i
	return slist

def newGame(rand): #performs new game actions
	global IS_DEAD
	for i in range(4, 8):
		luft_util.sendKey(i)
	time.sleep(2)
	luft_util.sendKey(2)
	time.sleep(.1)
	luft_util.sendKey(6)
	time.sleep(1)
	luft_util.sendKey(2)
	time.sleep(.1)
	luft_util.sendKey(6)
	IS_DEAD = False

def makeConvLayer(pData, channelN, filterN, filterS, poolS, strideN): #make conv layer
    conv_filterS = [filterS[0], filterS[1], channelN, filterN] #set up filter to scan image with
    weights = tf.Variable(tf.truncated_normal(conv_filterS, stddev=0.03)) #set random weights to begin with
    bias = tf.Variable(tf.truncated_normal([filterN])) #set random bias
    out_layer = tf.nn.conv2d(pData, weights, [1, strideN[0], strideN[1], 1], padding='SAME') #make out_layer by scanning image with filter
    out_layer += bias 
    out_layer = tf.nn.relu(out_layer) #pass out_layer through relu
    ksize = [1, poolS[0], poolS[1], 1]
    strides = [1, 2, 2, 1]
    out_layer = tf.nn.max_pool(out_layer, ksize=ksize, strides=strides, padding='SAME') #finish conv layer with pool

    return out_layer
	
def runConvNet(plen, nw, nh, lrt, rand): #the bulk of the python code
	global DSPOT
	global GAME_NUM
	global doRMove
	x = tf.placeholder(tf.float32, [1, nw, nh, 4]) #actual image

	mask = tf.placeholder(tf.float32, [8]) #stores which action was taken last time
	rt = tf.placeholder(tf.float32, [1]) #stores score at time of event
	nPred = tf.placeholder(tf.float32, [8]) #stores out_layer from first four screens

	L1 = makeConvLayer(x, 4, 32, [8, 8], [1, 1], [4, 4]) #run through conv net
	L2 = makeConvLayer(L1, 32, 64, [4, 4], [1, 1], [3, 3])
	L3 = makeConvLayer(L2, 64, 64, [3, 3], [1, 1], [1, 1])
	nlen = int(768) #as long as Luftrausers is at its default resolution, this works

	L3_flat = tf.reshape(L3, [1, nlen]) #stretch the output back out

	weight_d1 = tf.Variable(tf.truncated_normal([nlen, 512], stddev=0.03)) #run two fully connected layers
	bias_d1 = tf.Variable(tf.truncated_normal([512], stddev=0.01))
	denseL1 = tf.matmul(L3_flat, weight_d1) + bias_d1
	denseL1 = tf.nn.relu(denseL1)

	weight_out = tf.Variable(tf.truncated_normal([512, 8], stddev=0.03))
	bias_out = tf.Variable(tf.truncated_normal([8], stddev=0.01))
	out_layer = tf.matmul(denseL1, weight_out) + bias_out
	out_layer = tf.nn.relu(out_layer) #get actions probs for the controlls

	cost = (rt * mask + nPred * mask - np.amax(out_layer) * mask) ** 2 #make cost
	trainer = tf.train.AdamOptimizer(lrt).minimize(cost) #minimize cost

	saver = tf.train.Saver() #makes saver so we can save our net!

	sess = tf.Session()
	init = tf.global_variables_initializer().run(session=sess)

	cdir = os.path.dirname(os.path.realpath(__file__))
	saver.restore(sess, cdir+"\data\luft.ckpt") #one time load of previous net
	print("Loaded tensorflow net")

	#print(D_TABLE_sinit[0][0], "***")
	#print(D_TABLE_sinit[DSPOT-1][0], "***")
	#print(D_TABLE_sinit[DSPOT][0], "***")

	luft_util.sendKey(2) #start first game
	time.sleep(.1)
	luft_util.sendKey(6)
	time.sleep(.2)
	
	print("Starting loop")
	timeAlive = time.perf_counter()
	lkey = -1
	lscore = 0
	totScore = 0
	numGames = 0
	for i in range(60000+1): #LEARN THE GAME FOR A WHILE
		print("Step:", i, end="\r")

		if not rand: #if not making a new d_tablwxe, train

			if i % 200 == 0 and i != 0: #save net every 200 steps
				saver.save(sess, cdir+"\data\luft.ckpt")
				print("Saved net on step", i)

			elist = getShortList(4) #get events from d_table

			for e in elist: #train on every event in elist
				pInit = sess.run(out_layer, feed_dict={x: [D_TABLE_snext[e]]})[0] #run init screens through
				qsa = [0] * 8
				a = D_TABLE_a[e]
				qsa[a] = pInit[a] #make an array of all 0s except where the max of pInit was
				m = [0] * 8
				m[a] = 1 #make a mask of 0s except a 1 where the max of pInit was
				sess.run(trainer, feed_dict={x: [D_TABLE_sinit[e]], rt: [D_TABLE_r[e]], mask: m, nPred: qsa}) #finish training and update the weights

		if i % 1000 == 0 and i != 0: #if making a new d_table, save the d_table every n steps
			H5FILE.flush()
			print("Flushed d_table to file on step", i)

		en_sinit = np.zeros((nh*nw, 4), dtype=np.int8) #after training, make a new event
		en_r = 0
		en_a = 0
		for i in range(4):
			getImgData(plen, nw, nh, en_sinit, i)
			if IS_DEAD: #check if the AI died
				break;
		if not IS_DEAD:
			en_snext = np.copy(en_sinit)
			en_sinit = np.reshape(en_sinit, (nw, nh, 4))
			#print(pf)
			if not rand: #not making d_table, set normally
				pf = sess.run(out_layer, feed_dict={x: [en_sinit]})[0] #get suggested key for the current state
				if random.random() > doRMove:
					ksend = pf.argmax()
					if pf[ksend] != 0 and ksend != lkey:
						luft_util.sendKey(int(ksend)) #send the chosen key stroke and see what happens
						lkey = ksend
				else:
					ksend = random.randint(0, 7)
					if ksend != lkey:
						luft_util.sendKey(int(ksend)) #send the chosen key stroke and see what happens
						lkey = ksend
					if doRMove > .000001:
						doRMove -= .000001
			else: #else, set randomly
				ksend = random.randint(0, 7)
				if ksend != lkey:
					luft_util.sendKey(int(ksend)) #send the chosen key stroke and see what happens
					lkey = ksend

			luft_util.readGameMem(byref(SCORE)) #read score
			getImgData(plen, nw, nh, en_snext, 0)
			en_snext = np.reshape(en_snext, (nw, nh, 4))
			if IS_DEAD: #if AI died, don't add new event
				#timeAlive = time.perf_counter()
				lkey = -1
				numGames += 1
				totScore += SCORE[0]
				if numGames % 5 == 0:
					SCORE_AVG[GAME_NUM] = totScore/5
					print("Average Score over last 5 games:", (totScore/5))
					GAME_NUM += 1
					totScore = 0
				newGame(rand)
			else: #else, add event to spot DSPOT in d_table
				#nscore = SCORE[0] - int(1/((time.perf_counter()-timeAlive) / 1000.0))
				#if nscore < 0:
				#	nscore = 0
				#print(pf[ksend], keyCode[ksend], "Score:", nscore)
				if lscore == SCORE[0]:
					en_r = 0
				else:
					en_r = SCORE[1]
					lscore = SCORE[0]
				en_a = ksend
				np.copyto(D_TABLE_sinit[DSPOT], en_sinit)
				np.copyto(D_TABLE_snext[DSPOT], en_snext)
				D_TABLE_r[DSPOT] = en_r
				D_TABLE_a[DSPOT] = en_a


				
				DSPOT = (DSPOT + 1) % DLEN #change DSPOT
				D_TABLE_sinit.attrs["dspot"] = DSPOT

		else:
			#timeAlive = time.perf_counter()
			lkey = -1
			numGames += 1
			totScore += SCORE[0]
			if numGames % 5 == 0:
				SCORE_AVG[GAME_NUM] = totScore/5
				print("Average Score over last 5 games:", (totScore/5))
				GAME_NUM += 1
				totScore = 0
			newGame(rand)




luft_util = CDLL("cpp/luft_util.dll") #load luft_util dll
getPix = luft_util.getPix
getPix.restype = c_ulonglong #set getpix return type to avoid seg faults

luft_util.init() #init, very important
pixLen = luft_util.getPLen() #get image data
img_h = luft_util.getH()
img_w = luft_util.getW()
nimg_h = int(img_h/SHRINK) #adjust data
nimg_w = int(img_w/SHRINK)


if hdinit:
	H5FILE = h5py.File("data/d_table.hdf5", "w-")
	H5FILE.create_dataset("dtable/sinit", (DLEN, nimg_w, nimg_h, 4), dtype="i8", chunks=True, compression="lzf", shuffle=True)
	H5FILE.create_dataset("dtable/snext", (DLEN, nimg_w, nimg_h, 4), dtype="i8", chunks=True, compression="lzf", shuffle=True)
	H5FILE.create_dataset("dtable/r", (DLEN,), dtype="i", chunks=True, compression="lzf", shuffle=True)
	H5FILE.create_dataset("dtable/a", (DLEN,), dtype="i", chunks=True, compression="lzf", shuffle=True)
	H5FILE.create_dataset("avg", (2000000,), dtype="i", chunks=True, compression="lzf", shuffle=True)
	H5FILE["dtable"]["sinit"].attrs["dspot"] = 0
	H5FILE["avg"].attrs["game_num"] = 0
else: 	
	H5FILE = h5py.File("data/d_table.hdf5", "r+")
	D_TABLE_sinit = H5FILE["dtable"]["sinit"]
	D_TABLE_snext = H5FILE["dtable"]["snext"]
	D_TABLE_r = H5FILE["dtable"]["r"]
	D_TABLE_a = H5FILE["dtable"]["a"]
	SCORE_AVG = H5FILE["avg"]
	DSPOT = D_TABLE_sinit.attrs["dspot"]
	GAME_NUM = SCORE_AVG.attrs["game_num"]
	print("Loaded hdf5 file, DSPOT:", DSPOT)

	runConvNet(pixLen, nimg_w, nimg_h, l_rate, makeDTable) #start training

luft_util.closePMem() #free memory in luft_util
H5FILE.close()
