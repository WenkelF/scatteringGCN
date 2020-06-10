from __future__ import division
from __future__ import print_function
from utils import load_citation, accuracy
import time
import argparse
import numpy as np
from scipy import sparse

import torch
import torch.nn.functional as F
import torch.optim as optim
from models import GCN
# Training settings
parser = argparse.ArgumentParser()
parser.add_argument('--dataset', type=str, default="pubmed",help='Dataset to use.')
parser.add_argument('--no-cuda', action='store_true', default=False,
                    help='Disables CUDA training.')
parser.add_argument('--fastmode', action='store_true', default=False,
                    help='Validate during training pass.')
parser.add_argument('--seed', type=int, default=42, help='Random seed.')
parser.add_argument('--epochs', type=int, default=1000,
                    help='Number of epochs to train.')
parser.add_argument('--lr', type=float, default=0.01,
                    help='Initial learning rate.')
parser.add_argument('--weight_decay', type=float, default=5e-4,
                    help='Weight decay (L2 loss on parameters).')
parser.add_argument('--l1', type=float, default=0.0,
                    help='Weight decay (L1 loss on parameters).')
parser.add_argument('--hid1', type=int, default=13,
                    help='Number of hidden units.')
parser.add_argument('--hid2', type=int, default=14,
                    help='Number of hidden units.')
parser.add_argument('--smoo', type=float, default=1.0,
                    help='Smooth for Res layer')
parser.add_argument('--dropout', type=float, default=0.7,
                    help='Dropout rate (1 - keep probability).')
parser.add_argument('--normalization', type=str, default='AugNormAdj',
                    choices=['AugNormAdj'],
                    help='Normalization method for the adjacency matrix.')
parser.add_argument('--sct_inx1', type=int, default=0, help='scattering index1')
parser.add_argument('--sct_inx2', type=int, default=1, help='scattering index2.')
args = parser.parse_args()
args.cuda = not args.no_cuda and torch.cuda.is_available()
from torch.optim.lr_scheduler import MultiStepLR,StepLR

np.random.seed(args.seed)
torch.manual_seed(args.seed)
if args.cuda:
    torch.cuda.manual_seed(args.seed)

# Load data
#adj, features, labels, idx_train, idx_val, idx_test = load_data()
adj,A_tilde,adj_sct1,adj_sct2,adj_sct4,adj_sct8,adj_sct16, features, labels, idx_train, idx_val, idx_test = load_citation(args.dataset, args.normalization,args.cuda)
# Model and optimizer
model = GCN(nfeat=features.shape[1],
            para3=args.hid1,
            para4=args.hid2,
            nclass=labels.max().item() + 1,
            dropout=args.dropout,
            smoo=args.smoo)

optimizer = optim.Adam(model.parameters(),
                       lr=args.lr, weight_decay=args.weight_decay)
scheduler = MultiStepLR(optimizer, milestones=[100,200,300,400,500,600,700,800,900], gamma=0.9)

if args.cuda:
    model.cuda()
    features = features.cuda()
    A_tilde = A_tilde.cuda()
    adj = adj.cuda()
    labels = labels.cuda()
    idx_train = idx_train.cuda()
    idx_val = idx_val.cuda()
    idx_test = idx_test.cuda()


accu_list = []
time_list = []
start_time = time.time()
def train(epoch):
    t = time.time()
    model.train()
    optimizer.zero_grad()
    output = model(features,adj,A_tilde,adj_sct1,adj_sct2,adj_sct4,adj_sct8,adj_sct16,args.sct_inx1,args.sct_inx2)
    loss_train = F.nll_loss(output[idx_train], labels[idx_train])

    regularization_loss = 0
    for param in model.parameters():
        regularization_loss = torch.sum(torch.abs(param))

    loss_train = regularization_loss*args.l1+loss_train
    acc_train = accuracy(output[idx_train], labels[idx_train])
    loss_train.backward()
    optimizer.step()
    if not args.fastmode:
        # Evaluate validation set performance separately,
        # deactivates dropout during validation run.
        model.eval()
        output = model(features,adj,A_tilde,adj_sct1,adj_sct2,adj_sct4,adj_sct8,adj_sct16,args.sct_inx1,args.sct_inx2)
    loss_val = F.nll_loss(output[idx_val], labels[idx_val])
#    print(labels[idx_val].shape)
    acc_val = accuracy(output[idx_val], labels[idx_val])
#    print('Epoch: {:04d}'.format(epoch+1),
#          'loss_train: {:.4f}'.format(loss_train.item()),
#          'acc_train: {:.4f}'.format(acc_train.item()),
#          'loss_val: {:.4f}'.format(loss_val.item()),
#          'acc_val: {:.4f}'.format(acc_val.item()),
#          'time: {:.4f}s'.format(time.time() - t))
    accu_list.append(acc_val.item())
    time_list.append(time.time()-start_time)


def test():
    model.eval()
    output = model(features,adj,A_tilde,adj_sct1,adj_sct2,adj_sct4,adj_sct8,adj_sct16,args.sct_inx1,args.sct_inx2)
    loss_test = F.nll_loss(output[idx_test], labels[idx_test])
    acc_test = accuracy(output[idx_test], labels[idx_test])
    print('Hid1 %d, Hid2 %d'%(args.hid1,args.hid2))
    print("Test set results:",
          "loss= {:.4f}".format(loss_test.item()),
          "accuracy= {:.4f}".format(acc_test.item()))

# Train model
t_total = time.time()
for epoch in range(args.epochs):
    train(epoch)
    scheduler.step()
print("Optimization Finished!")
print("Total time elapsed: {:.4f}s".format(time.time() - t_total))

# Testing
test()

np.savetxt('sct_time.txt',time_list)
np.savetxt('sct_accu.txt',accu_list)