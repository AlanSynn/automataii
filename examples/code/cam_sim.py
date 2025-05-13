import pybullet as p
import pybullet_data
import time
import os

# URDF Content (from previous step)
urdf_content = """<?xml version="1.0"?>
<robot name="cam_follower_mechanism">

  <material name="pink">
    <color rgba="1 0.5 0.7 1"/>
  </material>
  <material name="blue">
    <color rgba="0.2 0.4 0.8 1"/>
  </material>
  <material name="light_blue_roller">
    <color rgba="0.5 0.7 1 1"/>
  </material>
  <material name="yellow_handle">
    <color rgba="1 0.9 0.2 1"/>
  </material>
  <material name="grey_metal">
    <color rgba="0.6 0.6 0.6 1"/>
  </material>

  <link name="base_link">
    <visual>
      <geometry>
        <box size="0.3 0.4 0.02"/> </geometry>
      <origin xyz="0 0 -0.01" rpy="0 0 0"/>
      <material name="grey_metal"/>
    </visual>
    <collision>
      <geometry>
        <box size="0.3 0.4 0.02"/>
      </geometry>
      <origin xyz="0 0 -0.01" rpy="0 0 0"/>
    </collision>
    <inertial>
      <mass value="5.0"/>
      <origin xyz="0 0 -0.01"/>
      <inertia ixx="0.1" ixy="0" ixz="0" iyy="0.1" iyz="0" izz="0.1"/>
    </inertial>
  </link>

  <link name="cam_assembly_link">
    <inertial>
      <mass value="1.0"/>
      <origin xyz="0 0 0"/> <inertia ixx="0.01" ixy="0" ixz="0" iyy="0.01" iyz="0" izz="0.01"/>
    </inertial>

    <visual name="shaft">
      <origin xyz="0 0 0" rpy="1.570796325 0 0"/> <geometry>
        <cylinder radius="0.02" length="0.25"/> </geometry>
      <material name="grey_metal"/>
    </visual>
    <collision name="shaft_collision">
      <origin xyz="0 0 0" rpy="1.570796325 0 0"/>
      <geometry>
        <cylinder radius="0.02" length="0.25"/>
      </geometry>
    </collision>

    <visual name="cam_body">
      <origin xyz="0.035 0 0" rpy="0 0 0"/> <geometry>
        <cylinder radius="0.07" length="0.04"/> </geometry>
      <material name="pink"/>
    </visual>
    <collision name="cam_body_collision">
      <origin xyz="0.035 0 0" rpy="0 0 0"/>
      <geometry>
        <cylinder radius="0.07" length="0.04"/>
      </geometry>
    </collision>

    <visual name="crank_arm">
      <origin xyz="0 -0.145 0.05" rpy="0 0 0"/> <geometry>
        <box size="0.03 0.04 0.1"/>
      </geometry>
      <material name="blue"/>
    </visual>
    <collision name="crank_arm_collision">
      <origin xyz="0 -0.145 0.05" rpy="0 0 0"/>
      <geometry>
        <box size="0.03 0.04 0.1"/>
      </geometry>
    </collision>

    <visual name="crank_handle">
      <origin xyz="0 -0.145 0.1" rpy="1.570796325 0 0"/> <geometry>
        <cylinder radius="0.02" length="0.08"/> </geometry>
      <material name="yellow_handle"/>
    </visual>
    <collision name="crank_handle_collision">
      <origin xyz="0 -0.145 0.1" rpy="1.570796325 0 0"/>
      <geometry>
        <cylinder radius="0.02" length="0.08"/>
      </geometry>
    </collision>
  </link>

  <link name="follower_rod_link">
    <inertial>
      <mass value="0.18"/>
      <origin xyz="0 0 0.075"/> <inertia ixx="0.001" ixy="0" ixz="0" iyy="0.001" iyz="0" izz="0.001"/>
    </inertial>
    <visual name="rod">
      <origin xyz="0 0 0.075" rpy="0 0 0"/> <geometry>
        <cylinder radius="0.015" length="0.15"/> </geometry>
      <material name="blue"/>
    </visual>
    <collision name="rod_collision">
      <origin xyz="0 0 0.075" rpy="0 0 0"/>
      <geometry>
        <cylinder radius="0.015" length="0.15"/>
      </geometry>
    </collision>
  </link>

  <link name="follower_roller_link">
    <inertial>
      <mass value="0.05"/>
      <origin xyz="0 0 0"/> <inertia ixx="0.0001" ixy="0" ixz="0" iyy="0.0001" iyz="0" izz="0.0001"/>
    </inertial>
    <visual name="roller">
      <origin xyz="0 0 0" rpy="0 1.570796325 0"/> <geometry>
        <cylinder radius="0.025" length="0.04"/> </geometry>
      <material name="light_blue_roller"/>
    </visual>
    <collision name="roller_collision">
      <origin xyz="0 0 0" rpy="0 1.570796325 0"/>
      <geometry>
        <cylinder radius="0.025" length="0.04"/>
      </geometry>
    </collision>
  </link>

  <joint name="cam_joint" type="revolute">
    <parent link="base_link"/>
    <child link="cam_assembly_link"/>
    <origin xyz="0 0 0.1" rpy="0 0 0"/> <axis xyz="0 1 0"/> <limit effort="1000" velocity="10" lower="-6.2831853" upper="6.2831853"/> <dynamics damping="0.01" friction="0.05"/>
  </joint>

  <joint name="follower_rod_joint" type="prismatic">
    <parent link="base_link"/>
    <child link="follower_rod_link"/>
    <origin xyz="0.035 0 0.09" rpy="0 0 0"/> <axis xyz="0 0 1"/> <limit effort="500" velocity="2.0" lower="0.0" upper="0.07"/>
    <dynamics damping="0.05" friction="0.1"/>
  </joint>

  <joint name="follower_roller_joint" type="continuous">
    <parent link="follower_rod_link"/>
    <child link="follower_roller_link"/>
    <origin xyz="0 0 0" rpy="0 0 0"/>
    <axis xyz="1 0 0"/> <dynamics damping="0.001" friction="0.005"/>
  </joint>

</robot>
"""

urdf_file_path = "cam_follower_mechanism.urdf"

# Write the URDF content to a file
with open(urdf_file_path, "w") as f:
    f.write(urdf_content)

# Initialize PyBullet
physicsClient = p.connect(p.GUI) # or p.DIRECT for non-graphical version
p.setAdditionalSearchPath(pybullet_data.getDataPath()) # For loading plane.urdf

# Setup simulation environment
p.setGravity(0, 0, -9.81)
p.setRealTimeSimulation(0) # We will step manually

# Load ground plane
planeId = p.loadURDF("plane.urdf")

# Load the cam-follower mechanism
# Initial orientation can be adjusted if needed, e.g. p.getQuaternionFromEuler([0,0,0])
startPos = [0, 0, 0.02] # Slightly above the ground plane
startOrientation = p.getQuaternionFromEuler([0, 0, 0])
robotId = p.loadURDF(urdf_file_path, startPos, startOrientation, useFixedBase=True) # Fix the base to the world

# Find the cam joint
num_joints = p.getNumJoints(robotId)
cam_joint_index = -1
cam_joint_name = "cam_joint"

print(f"Number of joints: {num_joints}")
for i in range(num_joints):
    joint_info = p.getJointInfo(robotId, i)
    j_name = joint_info[1].decode('UTF-8')
    j_type = joint_info[2]
    print(f"Joint {i}: Name={j_name}, Type={j_type}")
    if j_name == cam_joint_name:
        cam_joint_index = i
        break

if cam_joint_index == -1:
    print(f"Error: Could not find joint named '{cam_joint_name}'")
    p.disconnect()
    exit()

print(f"Found '{cam_joint_name}' at index {cam_joint_index}")

# Add a debug slider to control cam velocity
# Max force should be related to the 'effort' limit in URDF for the joint
# For velocity control, a high force limit allows the target velocity to be achieved if possible
max_force_cam = p.getJointInfo(robotId, cam_joint_index)[10] # Get maxForce from URDF limit
if max_force_cam == 0 : max_force_cam = 100 # Default if not specified or zero

velocity_slider = p.addUserDebugParameter("Cam Velocity", -5, 5, 2) # Range -5 to 5 rad/s, start at 2 rad/s

# Simulation parameters
time_step = 1.0/240.0 # Default PyBullet time step

# Set camera position for better view
p.resetDebugVisualizerCamera(cameraDistance=0.8, cameraYaw=30, cameraPitch=-25, cameraTargetPosition=[0,0,0.1])

print("\nStarting simulation. Close the PyBullet window to exit.")
print("Adjust the 'Cam Velocity' slider to change the cam's rotation speed.")

try:
    while p.isConnected():
        # Get desired velocity from slider
        target_velocity = p.readUserDebugParameter(velocity_slider)

        # Apply motor control to the cam joint
        p.setJointMotorControl2(
            bodyUniqueId=robotId,
            jointIndex=cam_joint_index,
            controlMode=p.VELOCITY_CONTROL,
            targetVelocity=target_velocity,
            force=max_force_cam # Apply enough force to achieve the velocity
        )

        # Step the simulation
        p.stepSimulation()

        # Optional: add a small delay to run at pseudo-real-time
        # For accurate physics, it's often better to rely on stepSimulation()
        # and let PyBullet manage timing internally if p.setRealTimeSimulation(1) is used.
        # Since we use p.setRealTimeSimulation(0), we control the step.
        time.sleep(time_step)

except p.error as e:
    print(f"PyBullet error: {e}")
except KeyboardInterrupt:
    print("Simulation interrupted by user.")
finally:
    if p.isConnected():
        p.disconnect()
    # Clean up the URDF file
    if os.path.exists(urdf_file_path):
        os.remove(urdf_file_path)
    print("Simulation ended and cleaned up.")