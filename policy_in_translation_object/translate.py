# -*- coding: utf-8 -*-
"""
@author: Jerry Zikun Chen
"""

from __future__ import print_function
import numpy as np
from torch.autograd import Variable
import torch
import sacrebleu
import time

global BOS_WORD_ID, EOS_WORD_ID
BOS_WORD_ID = 2
EOS_WORD_ID = 3


class Translation(object):
    def __init__(self, src, tgt, n_avlb, vocab, device, **kwargs,):
        """
        n_avlb: number of available word to choose at each step
        src: list of indices (SRC vocab) representing source sentence 
        vocab: target vocabulary (TGT.vocab.itos)
        """
        self.n_avlb = n_avlb
        self.vocab = np.array(vocab)
        self.src = np.array(src)  # list of indices
        self.tgt = np.array(tgt)  # list of indices
        self.output = np.array([2]) # index in the vocab
        # self.policy_value_net = policy_value_fn
        # self.device = policy_value_fn.device # change to device
        self.device = device
        # TODO: specifiy which dataset we are running on
        # If it is test set -> need to modify translation_end()
        # self.dataset = dataset 

    def init_state(self):
        # TO DO: policy_value input should be the current decoding state
        # pick highest 200 probability words
        # assume word_probs numpy array
        # if self.policy_value_net.use_gpu == True:
        #     src_tensor = torch.from_numpy(
        #         np.array(self.src).reshape(-1, 1)).to(self.device)
        #     dec_input = torch.from_numpy(
        #         np.array(self.output).reshape(-1, 1)).to(self.device)
        
        # log_word_probs, value, encoder_output = self.policy_value_net.policy_value(src_tensor, dec_input)
        # word_probs = np.exp(log_word_probs)

        # top_ids = np.argpartition(word_probs, -self.n_avlb)[-self.n_avlb:]
        # self.encoder_output = encoder_output.clone().detach() # store for later tranlstion output
        self.encoder_output = None
        self.availables = top_ids
        self.last_word_id = BOS_WORD_ID

    def current_state(self):
        # Q There are two outputs for now, does it fit with data buffer?
        return self.src, self.output

    def select_next_word(self, word_id):
        return self.vocab[word_id]

    def do_move(self, word_id):  # can change name to choose_word
        # word_id is the index in the vocab
        # TO DO: normalize other probabilities?
        # choose word
        self.last_word_id = word_id
        self.output = np.append(self.output, word_id)

        # choose top 200 words
        if self.policy_value_net.use_gpu == True:
            src_tensor = torch.from_numpy(
                    np.array(self.src).reshape(-1, 1)).to(self.device)
            dec_input = torch.from_numpy(
                    np.array(self.output).reshape(-1, 1)).to(self.device)

        log_word_probs, value, encoder_output = self.policy_value_net.policy_value(
                src_tensor, dec_input, self.encoder_output) # reusing encoder_output
        word_probs = np.exp(log_word_probs)
        top_ids = np.argpartition(word_probs, -self.n_avlb)[-self.n_avlb:]
        self.availables = top_ids
        

    def translation_end(self):
        """Check whether the translation is ended or not"""
        # print(self.output.tolist()[-1])
        if self.last_word_id == EOS_WORD_ID:
            # revert tokenization back to strings
            predict_tokens = self.vocab[self.output].tolist()
            ref_tokens = self.vocab[self.tgt].tolist()
            prediction_list = self.fix_sentence(predict_tokens)
            reference_list = self.fix_sentence(ref_tokens)
            prediction = ' '.join(word for word in prediction_list)
            reference = ' '.join(word for word in reference_list)
            print("reference: {}".format(reference))
            print("prediction: {}".format(prediction))
            # compute sacre BLEU score adjusted for length
            bleu = sacrebleu.corpus_bleu([prediction], [[reference]], smooth_method='exp').score / 100
            print("BLEU: {}".format(bleu))
            return True, bleu # TO DO return value output if end
        else:
            return False, -1

    def fix_sentence(self, sentence):
        """get original sentences from tokenizations"""
        sentence = sentence[1:-2]
        new_sentence = []
        cur_word = ''
        for p in sentence:
            if '@@' in p:
                cur_word += p[:-2]
            else:
                if cur_word != '':
                    new_sentence.append(cur_word+p)
                    cur_word = ''
                elif '&' in p and ';' in p:  # this means should be adding this onto last added word
                    if len(new_sentence) > 0:
                        new_sentence[-1] = new_sentence[-1] + \
                            "'"+p.split(';')[1]
                    # OTHERWISE NOT SURE WHAT TO DO
                    else:
                        pass  # NEED TO IMPLEMENT
                else:
                    new_sentence.append(p)
        return new_sentence

class Translate(object):
    """game server"""

    def __init__(self, translation, **kwargs):
        self.translation = translation

    def graphic(translation):
        pass

    def start_train_translate(self, translator, is_shown=0, temp=1e-3):
        """ start a translation using a MCTS player, reuse the search tree,
            and store the translation data: (state, mcts_probs, z) for training
            state: list of current states (src, output) of tranlations
            mcts_probs: list of probs
            bleus_z: list of bleu scores
        """
        self.translation.init_state()
        states, mcts_probs, bleus_z = [], [], []
        while True:
            # 55 seconds per loop (100 simulations)
            start_time = time.time()
            word_id, word_probs = translator.get_action(self.translation,
                                                        temp=temp,
                                                        return_prob=1)
            # store the data
            # a tuple of (src, output)
            states.append((self.translation.current_state()))
            mcts_probs.append(word_probs)
            # choose a word (perform a move)
            self.translation.do_move(word_id)
            end, bleu = self.translation.translation_end()
            
            print("states collected: {}".format(states))
            print("mcts_probs collected: {}".format(mcts_probs))
            print("time: {}".format(time.time() - start_time))

            if end:
                bleus_z.append(bleu)
                # reset MCTS root node
                print("bleus_z collected: {}".format(bleus_z))
                print("sentence produced: {}".format(self.translation.vocab[output].tolist()))
                return bleu, zip(states, mcts_probs, bleus_z)

