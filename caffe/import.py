'''Import layer params from disk to rebuild the caffemodel.'''

from __future__ import print_function

import os
os.environ['GLOG_minloglevel'] = '2'  # Hide caffe debug info.

import json
import caffe
import numpy as np
import sys
from caffe import layers as L


# Directory containing layer param and config file.
PARAM_DIR = './output/param/'
CONFIG_DIR = './output/config/'


def input_layer(layer_config):
    input_shape = layer_config['input_shape']
    return L.DummyData(shape=[dict(dim=input_shape)], ntop=1)

def conv_layer(layer_config, bottom_name):
    num_output = layer_config['num_output']
    kW, kH = layer_config['kW'], layer_config['kH']
    dW, dH = layer_config['dW'], layer_config['dH']
    pW, pH = layer_config['pW'], layer_config['pH']

    return L.Convolution(num_output=num_output,
                         bottom=bottom_name,
                         kernel_w=kW,
                         kernel_h=kH,
                         stride_w=dW,
                         stride_h=dH,
                         pad_w=pW,
                         pad_h=pH)

def bn_layer(layer_config, bottom_name):
    return L.BatchNorm(bottom=bottom_name,
                       use_global_stats=True)

def scale_layer(layer_config, bottom_name):
    return L.Scale(bottom=bottom_name,
                   bias_term=True)

def relu_layer(layer_config, bottom_name):
    '''For ReLU layer, top=bottom'''
    return L.ReLU(bottom=bottom_name, top=bottom_name, in_place=True)

def tanh_layer(layer_config, bottom_name):
    '''For ReLU layer, top=bottom'''
    return L.TanH(bottom=bottom_name, top=bottom_name, in_place=True)

def pool_layer(layer_config, bottom_name):
    pool_type = layer_config['pool_type']
    kW, kH = layer_config['kW'], layer_config['kH']
    dW, dH = layer_config['dW'], layer_config['dH']
    pW, pH = layer_config['pW'], layer_config['pH']

    return L.Pooling(bottom=bottom_name,
                     pool=pool_type,
                     kernel_w=kW,
                     kernel_h=kH,
                     stride_w=dW,
                     stride_h=dH,
                     pad_w=pW,
                     pad_h=pH)

def flatten_layer(layer_config, bottom_name):
    return L.Flatten(bottom=bottom_name)

def linear_layer(layer_config, bottom_name):
    num_output = layer_config['num_output']
    return L.InnerProduct(bottom=bottom_name,
                          num_output=num_output)

def softmax_layer(layer_config, bottom_name):
    return L.Softmax(bottom=bottom_name)

def build_prototxt():
    '''Build a new prototxt from config file.

    Save as `cvt_net.prototxt`.
    '''
    print('==> Building prototxt..')

    # Map layer_type to its building function.
    layer_fn = {
        'Data': input_layer,
        'DummyData': input_layer,
        'Convolution': conv_layer,
        'BatchNorm': bn_layer,
        'Scale': scale_layer,
        'ReLU': relu_layer,
        'TanH': tanh_layer,
        'Pooling': pool_layer,
        'Flatten': flatten_layer,
        'InnerProduct': linear_layer,
        'Softmax': softmax_layer
    }

    net = caffe.NetSpec()

    with open(CONFIG_DIR + 'net.json', 'r') as f:
        net_config = json.load(f)

    # Add input layer.
    print('... Add layer: DummyData')
    input_layer_name = net_config[0]['name']
    net[input_layer_name] = input_layer(net_config[0])

    # DFS graph to build prototxt.
    graph = np.load(CONFIG_DIR + 'graph.npy')
    num_nodes = graph.shape[0]
    marked = [False for i in range(num_nodes)]

    
    def dfs(G, v, pre_flag):
        marked[v] = True

        if pre_flag is None:
            pass
        else:
            pre_trans_flag = pre_flag
        
        bottom_layer_name = net_config[v]['name']
        #print(v)
        #print(bottom_layer_name)
        if v > 0:
            pre_bottom_layer_name = net_config[v-1]['name']
            #print(pre_bottom_layer_name)
        for w in range(num_nodes):
            if G[v][w] == 1 and not marked[w]:
                layer_config = net_config[w]
                print(layer_config)
                print('--------------------')
                layer_name = layer_config['name']
                layer_type = layer_config['type']

                print('... Add layer: %s' % layer_type)
                get_layer = layer_fn.get(layer_type)
                if not get_layer:
                    raise TypeError('%s not supported yet!' % layer_type)
                
                #print(layer_type)
                #print('BLN:%s'% bottom_layer_name)
                #print(pre_trans_flag)
                #if v>0:
                #    print('PBLN:%s'% pre_bottom_layer_name)

                if pre_trans_flag == True:
                    layer = get_layer(layer_config, pre_bottom_layer_name)
                    pre_trans_flag = False
                else:    
                    layer = get_layer(layer_config, bottom_layer_name)
                
                if layer_type == 'ReLU' or layer_type == 'TanH':
                    pre_trans_flag = True

                net[layer_name] = layer
                dfs(G, w, pre_trans_flag)

    # DFS.
    dfs(graph, 0, False)

    # Save prototxt.
    with open('./output/cvt_net.prototxt', 'w') as f:
        f.write(str(net.to_proto()))
        print('Saved!\n')

def load_param(layer_name):
    '''Load saved layer params.

    Returns:
      (tensor) weight or running_mean or None.
      (tensor) bias or running_var or None.
    '''
    weight_path = PARAM_DIR + layer_name + '.w.npy'
    bias_path = PARAM_DIR + layer_name + '.b.npy'

    weight = np.load(weight_path) if os.path.isfile(weight_path) else None
    bias = np.load(bias_path) if os.path.isfile(bias_path) else None

    return weight, bias

def fill_params():
    '''Fill network with saved params.

    Save as `cvt_net.caffemodel`.
    '''
    print('==> Filling layer params..')

    net = caffe.Net('./output/cvt_net.prototxt', caffe.TEST)
    for i in range(len(net.layers)):
        layer_name = net._layer_names[i]
        layer_type = net.layers[i].type

        print('... Layer %d : %s' % (i, layer_type))

        weight, bias = load_param(layer_name)

        if weight is not None:
            net.params[layer_name][0].data[...] = weight
        if bias is not None:
            net.params[layer_name][1].data[...] = bias

        if layer_type == 'BatchNorm':
            net.params[layer_name][2].data[...] = 1.  # use_global_stats=true

    net.save('./output/cvt_net.caffemodel')
    print('Saved!')


if __name__ == '__main__':
    # Build new prototxt based on config file.
    build_prototxt()

    # Fill network with saved params.
    fill_params()
