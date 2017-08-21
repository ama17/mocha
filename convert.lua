require('nn')


net = torch.load('model.t7')
print(net)
torch.save('net.t7',net)

cmd = 'th torch/export.lua ./net.t7 {1,3,55,55}'
os.execute(cmd)

cmd = 'python caffe/import.py'
os.execute(cmd)



