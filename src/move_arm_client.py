#!/usr/bin/env python3

import rospy
from manipulator_gazebo.srv import *
from std_msgs.msg import Float64
from sensor_msgs.msg import JointState
import math
import time
import ipfshttpclient
import rospkg
import json
from substrateinterface import SubstrateInterface, Keypair


class Kuka:
    def __init__(self):
        rospy.init_node('listener', anonymous=False)
        rospack = rospkg.RosPack()
        rospack.list()
        self.path = rospack.get_path('kuka_controller')
        with open(f"{self.path}/config/config", "r") as f:
            config = json.load(f)
        self.client = ipfshttpclient.connect()
        self.substrate = SubstrateInterface(
            url=config["node"],
            ss58_format=32,
            type_registry_preset="substrate-node-template",
            type_registry={
                "types": {
                    "Record": "Vec<u8>",
                    "Parameter": "Bool",
                    "LaunchParameter": "Bool",
                    "<T as frame_system::Config>::AccountId": "AccountId",
                    "RingBufferItem": {
                        "type": "struct",
                        "type_mapping": [
                            ["timestamp", "Compact<u64>"],
                            ["payload", "Vec<u8>"],
                        ],
                    },
                    "RingBufferIndex": {
                        "type": "struct",
                        "type_mapping": [
                            ["start", "Compact<u64>"],
                            ["end", "Compact<u64>"],
                        ],
                    }
                }
            },
        )
        mnemonic = config["kuka_mnemonic"]
        self.keypair = Keypair.create_from_mnemonic(mnemonic, ss58_format=32)

    # Call service move_arm
    def move_arm_client(self, desired_xyz, duration):
        rospy.wait_for_service('move_arm')
        try:
            move_arm = rospy.ServiceProxy('move_arm', MoveArm)
            resp = move_arm(desired_xyz, duration)
            return resp
        except rospy.ServiceException as e:
            rospy.loginfo("Service call failed: %s"%e)

    # Write data to a file
    def listener(self, data):
        if self.write:
            times_prev = self.times
            self.times = int(time.time())
            if self.times != times_prev:
                #print('write')
                self.logs.write('\n')
                self.logs.write(str(data))
    
    def write_datalog(self, data):
        call = self.substrate.compose_call(
            call_module="Datalog",
            call_function="record",
            call_params={
                'record': data
            }
        )
        extrinsic = self.substrate.create_signed_extrinsic(call=call, keypair=self.keypair)
        receipt = self.substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
        rospy.loginfo(f"Datalog created with extrinsic hash: {receipt.extrinsic_hash}")

    # Print circle
    def circle(self):
        rospy.loginfo("Work paid. Starting work...")
        t = 0
        self.logs = open(f'{self.path}/data.txt', 'w')
        self.move_arm_client([Float64(0.3), Float64(0.3), Float64(0.6)], Float64(2.0))
        self.times = 0
        self.write = True
        rospy.Subscriber('/manipulator/joint_states', JointState, self.listener)
        while t <= math.pi:
            x = 0.3*math.cos(t)
            z = 0.3*math.sin(t) + 0.6
            t += 0.2
            #print(x, z)
            self.move_arm_client([Float64(x), Float64(0.3), Float64(z)], Float64(0.05))
        self.write = False
        rospy.loginfo("Work done")
        self.logs.close()
        res = self.client.add(f'{self.path}/data.txt')
        rospy.loginfo(f"Data pinned to IPFS with hash {res['Hash']}")
        self.write_datalog(res['Hash'])
        rospy.loginfo(f"Wait for payment")

    def subscription_handler(self, obj, update_nr, subscription_id):
        ch = self.substrate.get_chain_head()
        chain_events = self.substrate.get_events(ch)
        for ce in chain_events:
                # if ce.value["event_id"] == "NewLaunch":
                #     print(ce.params)
                if ce.value["event_id"] == "NewLaunch" and ce.params[1]["value"] == self.keypair.ss58_address \
                                             and ce.params[2]["value"] is True:  # yes/no
                    print(f"\"ON\" launch command from employer.")
                    self.circle()


    def spin(self):
        rospy.loginfo(f"Wait for payment")
        self.substrate.subscribe_block_headers(self.subscription_handler)


if __name__ == "__main__":
    Kuka().spin()
        
