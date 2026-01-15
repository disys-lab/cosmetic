from MerkleProver import MerkleProver
import torch, os, sys
from aggregators.Adder import Adder #,AdderNumericCheck
from transformers.FlowThrough import FlowThrough
from transformers.Affine import Affine
from transformers.Exponent import Exponent
from transformers.Length import Length
from transformers.LogisticLogLikelihood import LogLogLikelihood
# torch.manual_seed(1337)

TEST_INCLUSION= True
TEST_EXCLUSION= True

use_zkp = int(os.environ.get("ZKP_MODE",1))
gen_full_proof = int(os.environ.get("GEN_FULL_PROOF",0))
setup_mrp = int(os.environ.get("SETUP_MRP",0))
setup_ltr = int(os.environ.get("SETUP_LTR",0))
id = os.environ.get("ID",None)
ltr_choice = os.environ.get("LTR_CHOICE","flow-through")

user_data = "s&p_loglikelihood_debug"

zkp_scale=8

rand_bit=1

if user_data == "original_driver_data":
    record_shape = 1
    salt_shape = 2
    transform_salt_shape=2
    total_shape = salt_shape + record_shape
    alice_salt = rand_bit*torch.randint(high=2**5-1,size=(salt_shape,),dtype=torch.float32,)
    bob_salt = rand_bit*torch.randint(high=2**5-1,size=(salt_shape,),dtype=torch.float32,)
    carol_salt = rand_bit*torch.randint(high=2**5-1,size=(salt_shape,),dtype=torch.float32,)
    dave_salt = rand_bit*torch.randint(high=2**5-1,size=(salt_shape,),dtype=torch.float32,)


    transform_salt_alice = rand_bit*torch.randint(high=2**15-1,size=(1,transform_salt_shape),dtype=torch.float32,) #torch.randn(transform_salt_shape).reshape(1,transform_salt_shape)
    transform_salt_bob = rand_bit*torch.randint(high=2**15-1,size=(1,transform_salt_shape),dtype=torch.float32,) #torch.randn(transform_salt_shape).reshape(1,transform_salt_shape)
    transform_salt_carol = rand_bit*torch.randint(high=2**15-1,size=(1,transform_salt_shape),dtype=torch.float32,) #torch.randn(transform_salt_shape).reshape(1,transform_salt_shape)
    transform_salt_dave = rand_bit*torch.randint(high=2**15-1,size=(1,transform_salt_shape),dtype=torch.float32,) #torch.randn(transform_salt_shape).reshape(1,transform_salt_shape)
    raw_data = [
        {"name": 'alice', "value": torch.cat([torch.tensor([2,],dtype=torch.float32),alice_salt],dim=0).reshape(1,total_shape),"transform_salt":transform_salt_alice},
        {"name": 'bob', "value": torch.cat([torch.tensor([4,],dtype=torch.float32),bob_salt],dim=0).reshape(1,total_shape),"transform_salt":transform_salt_bob},
        {"name": 'carol', "value": torch.cat([torch.tensor([3,],dtype=torch.float32),carol_salt],dim=0).reshape(1,total_shape),"transform_salt":transform_salt_carol},
        {"name": 'dave', "value": torch.cat([torch.tensor([4,],dtype=torch.float32),dave_salt],dim=0).reshape(1,total_shape),"transform_salt":transform_salt_dave}
     ]

    transform_absent_salt = rand_bit * torch.randint(high=2 ** 5 - 1, size=(salt_shape,))
    test_absent_data_record = {"name": 'ruth', "value": torch.cat([torch.tensor([31, ]), bob_salt], dim=0),"transform_salt": transform_absent_salt}


elif user_data == "s&p_loglikelihood_debug":
    # transform_salt_shape = 2
    # user_record_shape = 16
    # total_shape = 16

    record_shape = 6
    salt_shape = 10
    transform_salt_shape=2
    total_shape = salt_shape + record_shape

    raw_data= [
    {'name': 'user_1', 'value': torch.tensor([[ 1.,  0.,  0.,  0.,  1.,  1.,  0.,  3., 29., 15., 29., 25., 15.,  0., 16., 16.]]), 'transform_salt': torch.tensor([[26438.,  3938.]])},
    {'name': 'user_2', 'value': torch.tensor([[ 1.,  0.,  0.,  0.,  1.,  1., 27.,  8.,  9.,  5.,  0., 17., 27.,  1., 30., 16.]]), 'transform_salt': torch.tensor([[1000., 9959.]])},
    {'name': 'user_3', 'value': torch.tensor([[ 1.,  0.,  0.,  0.,  0.,  1., 12., 28., 26.,  9., 10., 23., 26.,  1., 9., 30.]]), 'transform_salt': torch.tensor([[ 3394., 31609.]])},
    {'name': 'user_4', 'value': torch.tensor([[ 1.,  0.,  0.,  0.,  1.,  1., 27., 17., 21., 31., 10., 16.,  5., 21., 2.,  2.]]), 'transform_salt': torch.tensor([[31795., 17222.]])},
    {'name': 'user_5', 'value': torch.tensor([[ 1.,  0.,  0.,  0.,  0.,  0.,  4.,  0., 17.,  7., 19., 27., 17.,  5., 5., 14.]]), 'transform_salt': torch.tensor([[ 5243., 16835.]])},
    {'name': 'user_6', 'value': torch.tensor([[ 1.,  0.,  0.,  0.,  1.,  0., 27.,  8.,  8., 21., 16., 13.,  9., 18., 29., 14.]]), 'transform_salt': torch.tensor([[12468.,  3887.]])},
    {'name': 'user_7', 'value': torch.tensor([[ 1.,  0.,  0.,  0.,  0.,  0., 20., 12.,  2., 12.,  0., 16., 25.,  5., 4., 18.]]), 'transform_salt': torch.tensor([[ 3341., 22357.]])},
    {'name': 'user_8', 'value': torch.tensor([[ 1.,  0.,  1.,  0.,  0.,  1., 12., 13.,  6., 15., 25., 20.,  8., 12., 14., 23.]]), 'transform_salt': torch.tensor([[29313., 19885.]])},
    {'name': 'user_9', 'value': torch.tensor([[ 1.,  0.,  0.,  0.,  1.,  0., 21.,  3., 15.,  5., 10.,  3., 30., 11., 27., 24.]]), 'transform_salt': torch.tensor([[ 7565., 13034.]])},
    {'name': 'user_10', 'value': torch.tensor([[ 1.,  0.,  0.,  0.,  1.,  0., 26., 10., 21., 20., 21., 12., 15., 22., 7., 24.]]), 'transform_salt': torch.tensor([[12839., 21573.]])},
    {'name': 'user_11', 'value': torch.tensor([[ 1.,  0.,  0.,  0.,  0.,  0., 23., 18.,  8.,  2.,  0.,  2.,  1., 16., 19.,  6.]]), 'transform_salt': torch.tensor([[24693., 23884.]])},
    {'name': 'user_12', 'value': torch.tensor([[ 1.,  0.,  0.,  0.,  1.,  0., 31., 24.,  5.,  3., 26., 21., 10.,  3., 3., 14.]]), 'transform_salt': torch.tensor([[14952., 16336.]])}]

    transform_absent_salt = rand_bit * torch.randint(high=2 ** 15 - 1, size=(1,transform_salt_shape,))
    test_absent_data_record = {'name': 'user_11', 'value': torch.tensor([[ 1.,  0.,  0.,  0.,  0.,  0., 26., 10., 21., 20., 21., 12., 15., 22., 7., 24.]]), "transform_salt": transform_absent_salt}

else:
    sys.exit(1)

raw_default_value = torch.zeros_like(raw_data[0]["value"])

#declare the aggregator
aggregator = Adder()

#exponent transformer
if ltr_choice == "exponent":
    transformer = Exponent(length_transform_salt=transform_salt_shape,exponent=0)

#affine transformer
elif ltr_choice == "affine":
    transformer = Affine(length_transform_salt=transform_salt_shape,slope=torch.tensor([2],dtype=torch.float32).reshape(1,1),intercept=torch.tensor([1],dtype=torch.float32).reshape(1,1))

#length transformer
elif ltr_choice == "length":
    transformer = Length(length_transform_salt=transform_salt_shape)

elif ltr_choice == "logll":
    transformer = LogLogLikelihood(length_transform_salt=transform_salt_shape,beta=torch.tensor([2,1,0,3,4],dtype=torch.float32).reshape(5,1))

#declare the transformer
else:
    transformer = FlowThrough(length_transform_salt=transform_salt_shape)

#initialize the merkle prover
mrp = MerkleProver(prover_name=f"simple_sum_{ltr_choice}",id=id,aggregator=aggregator,transformer=transformer,raw_data=raw_data,raw_default_value=raw_default_value,length_transform_salt=transform_salt_shape,setup_mrp=use_zkp&setup_mrp,setup_ltr=use_zkp&setup_ltr)

#build the merkle tree
mrp._build_smt()

#print the root value and hash
print(f"Root Value:{mrp.root_value}")
print(f"Root Hash:{mrp.root_hash}")


if TEST_INCLUSION:
    mrp._print_section_header("INCLUSION TEST: Picking raw data value that exists")
    #check for inclusion
    #proof check for record that is present
    test_present_data_record = raw_data[2]

    transformed_hash, raw_hash_present = mrp.transform_individual_data_record(raw_test_record=test_present_data_record)

    mrp.test_inclusion(transformed_hash)
    nonce = torch.randn(total_shape+transform_salt_shape).reshape(1,total_shape+transform_salt_shape)
    # mrp.path_walk(raw_hash_present,nonce,use_zkp=False,gen_full_proof=gen_full_proof)
    mrp.path_walk(raw_value_hash=raw_hash_present,nonce=nonce,use_zkp=use_zkp,gen_full_proof=gen_full_proof)

if TEST_EXCLUSION:
    mrp._print_section_header("EXCLUSION TEST: Picking raw data value that does not exist")

    #check for exclusion
    #proof check for record that is absent

    transformed_hash, raw_hash_absent = mrp.transform_individual_data_record(raw_test_record=test_absent_data_record)

    mrp.test_inclusion(transformed_hash)

    nonce = torch.randn(total_shape+transform_salt_shape).reshape(1,total_shape+transform_salt_shape)
    # mrp.path_walk(raw_hash_absent,nonce,use_zkp=False,gen_full_proof=gen_full_proof)
    mrp.path_walk(data_record=test_absent_data_record,nonce=nonce,use_zkp=use_zkp,gen_full_proof=gen_full_proof)