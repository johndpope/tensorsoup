import tensorflow as tf
import numpy as np

import sys
sys.path.append('../../')

from sanity import *
from models.memorynet.modules import *

from collections import OrderedDict


class MemoryNet(object):

    def __init__(self, hdim, num_hops, 
            memsize, sentence_size, qlen, 
            vocab_size, num_candidates):

        # reset graph
        tf.reset_default_graph()

        # initializer
        self.init = tf.random_normal_initializer(0, 0.1)

        # num of copies of model (for multigpu training)
        self.n = 1

        #optimizer = tf.train.AdamOptimizer(learning_rate=lr)

        def inference():

            with tf.name_scope('input'):
                # build placeholders
                questions = tf.placeholder(tf.int32, shape=[None, qlen], 
                                           name='questions' )
                stories = tf.placeholder(tf.int32, shape=[None, memsize, sentence_size],
                                         name='stories' )

                answers = tf.placeholder(tf.int32, shape=[None, ],
                                         name='answers' )
                # default placeholders
                mode = tf.placeholder(tf.int32, shape=[], name='mode')
                lr = tf.placeholder(tf.float32, shape=[], name='lr')
                
            # expose handle to placeholders
            placeholders = OrderedDict()
            placeholders['questions'] = questions
            placeholders['stories'] = stories
            placeholders['answers'] = answers

            # inject noise to memories
            dropout = tf.random_uniform([memsize, 1], 0, 1) > 0.1
            # shape to match stories
            dropout = tf.cast(dropout, tf.int32)* tf.ones(
                    [memsize, sentence_size], tf.int32)
            noisy_stories = stories * dropout

            _stories = tf.cond(mode<2,
                        lambda : noisy_stories,
                        lambda : stories)

            # position encoding
            sent_encoding = tf.constant(self.position_encoding(sentence_size, hdim))
            ques_encoding = tf.constant(self.position_encoding(qlen, hdim))

            # embedding
            with tf.name_scope('embeddings'):
                A = mask_emb(tf.get_variable('A', 
                    shape=[num_hops, vocab_size, hdim], 
                    dtype=tf.float32, 
                    initializer=self.init))

                B = mask_emb(tf.get_variable('B', 
                    shape=[vocab_size, hdim], 
                    dtype=tf.float32, 
                    initializer=self.init))

                C = mask_emb(tf.get_variable('C', 
                    shape=[num_hops, vocab_size, hdim], 
                    dtype=tf.float32, 
                    initializer=self.init))

            with tf.name_scope('question'):
                # embed questions
                u0 = tf.nn.embedding_lookup(B, questions)
                u0 = tf.reduce_sum(u0*ques_encoding, axis=1)
                u = [u0] # accumulate question emb

            with tf.name_scope('temporal'):
                # more variables
                H = tf.get_variable('H', dtype=tf.float32, shape=[hdim, hdim],
                        initializer=self.init)
                TA = tf.get_variable('TA', dtype=tf.float32, shape=[num_hops, memsize, hdim],
                        initializer=self.init)
                TC = tf.get_variable('TC', dtype=tf.float32, shape=[num_hops, memsize, hdim],
                        initializer=self.init)

            with tf.name_scope('memloop'):
                # memory loop
                for i in range(num_hops):
                    # embed stories
                    m = tf.nn.embedding_lookup(A[i], _stories)
                    m = tf.reduce_sum(m*sent_encoding, axis=2) + TA[i]
                    c = tf.nn.embedding_lookup(C[i], _stories)
                    c = tf.reduce_sum(c, axis=2) + TC[i]

                    score = tf.reduce_sum(m*tf.expand_dims(u[-1], axis=1), axis=-1)
                    p = tf.cond(mode>0,
                                lambda : tf.nn.softmax(score),
                                lambda : score)
                    o = tf.reduce_sum(tf.expand_dims(p, axis=-1)*c, axis=1)
                    u_k = tf.matmul(u[-1], H) + o
                    u.append(u_k)

            with tf.name_scope('output'):
                # answer selection
                W = tf.get_variable('W', dtype=tf.float32, shape=[hdim, num_candidates],
                                   initializer=self.init)
                logits = tf.matmul(u[-1], W)

            with tf.name_scope('loss'):
                # optimization
                cross_entropy = tf.nn.sparse_softmax_cross_entropy_with_logits(
                    logits=logits,
                    labels=answers
                    )
                # attach loss to instance
                #loss = tf.reduce_sum(cross_entropy)
                loss = cross_entropy

            with tf.name_scope('evaluation'):
                # evaluation
                probs = tf.nn.softmax(logits)
                correct_labels = tf.equal(tf.cast(answers, tf.int64), tf.argmax(probs, axis=-1))
                accuracy = tf.reduce_mean(tf.cast(correct_labels, tf.float32))

            with tf.name_scope('optimization'):
                # gradient clipping
                optimizer = tf.train.AdamOptimizer(learning_rate=lr)
                #optimizer = tf.train.GradientDescentOptimizer(learning_rate=lr)
                gvs = optimizer.compute_gradients(loss)
                clipped_gvs = [(tf.clip_by_norm(grad, 40.), var) for grad, var in gvs]
                self.train_op = optimizer.apply_gradients(clipped_gvs)

            self.loss = tf.reduce_mean(loss)
            self.accuracy = accuracy
            self.stories = stories
            self.questions = questions
            self.answers = answers
            self.mode = mode
            self.lr = lr
            
            self.placeholders = [stories, questions, answers]


        inference()


    def position_encoding(self, slen, embedding_size):

        encoding = np.ones((embedding_size, slen), dtype=np.float32)
        ls = slen+1
        le = embedding_size+1
        for i in range(1, le):
            for j in range(1, ls):
                encoding[i-1, j-1] = (i - (le-1)/2) * (j - (ls-1)/2)
        encoding = 1 + 4 * encoding / embedding_size / slen
        return np.transpose(encoding)
