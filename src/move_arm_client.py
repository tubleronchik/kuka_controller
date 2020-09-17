#!/usr/bin/env python

import rospy
from manipulator_gazebo.srv import *
from std_msgs.msg import Float64
from sensor_msgs.msg import JointState
import math
import os
import ConfigParser
import subprocess
import time
import ipfshttpclient

kuka_address = "5GFAWEKfV6awpZUzAcuPaBjZaHDGoi37BkmjE5mxRcbvkxY1"
kuka_key = "0xe6a576226ab22016c7873f15922e9ec2ff59498260ebdb7b39337214370422c4"
work_address = "5Ci61tCV7GgooiCb8W2jnZFsdSTfURCVpXPXS5JCAdqRGFiQ"
robonomics_path = "/home/alena/"

rospy.init_node('listener', anonymous=False)
client = ipfshttpclient.connect()

# Call service move_arm
def move_arm_client(desired_xyz, duration):
    rospy.wait_for_service('move_arm')
    try:
        move_arm = rospy.ServiceProxy('move_arm', MoveArm)
        resp = move_arm(desired_xyz, duration)
        return resp
    except rospy.ServiceException as e:
        print("Service call failed: %s"%e)

# Write data to a file
def listener(data):
    if write:
        global times
        times_prev = times
        times = int(time.time())
        if times != times_prev:
            #print('write')
            f.write('\n')
            f.write(str(data))

# Print circle
def circle():
    t = 0
    global f
    f = open('data.txt', 'w')
    move_arm_client([Float64(0.3), Float64(0.3), Float64(0.6)], Float64(2.0))
    global times
    times = 0
    global write
    write = True
    while t <= math.pi:
        rospy.Subscriber('/manipulator/joint_states', JointState, listener)
        x = 0.3*math.cos(t)
        z = 0.3*math.sin(t) + 0.6
        t += 0.2
        #print(x, z)
        move_arm_client([Float64(x), Float64(0.3), Float64(z)], Float64(0.05))
    write = False
    print("Work done")
    f.close()
    res = client.add('data.txt')
    #print(res['Hash'])
    command = "echo \"Hash: " + res['Hash'] + "\" | " + robonomics_path + "robonomics io write datalog -s " + kuka_key
    send_datalog = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    print("Data sent to IPFS")

if __name__ == "__main__":
    work_paid = True
    proc = robonomics_path + "robonomics io read launch"
    process = subprocess.Popen(proc, shell=True, stdout=subprocess.PIPE)
    #while True:
    if work_paid:
        print("Waiting for payment")
    try:
        output = process.stdout.readline()
        if output.strip() == work_address + " >> " + kuka_address + " : true":
            print("Work paid")
            work_paid = True
            circle()
        else:
            work_paid = False

    except KeyboardInterrupt:
        exit()
        
