# 📊 PIPER RViz 시각화 가이드

## 🎯 개요

RViz를 통해 PIPER 로봇의 실시간 상태를 3D로 시각화할 수 있습니다.

### 주요 기능
- ✅ 실시간 관절 각도 표시
- ✅ End effector 위치 표시
- ✅ 그리퍼 상태 시각화
- ✅ TF 트리 시각화
- ✅ 로봇 동작 궤적 추적

## 🚀 빠른 시작

### 1. 기본 실행 (RViz 포함)
```bash
# 터미널 1: ROS 코어 (이미 실행 중이면 생략)
roscore

# 터미널 2: RViz 실행
roslaunch piper_rviz.launch

# 터미널 3: 텔레오퍼레이션
python3 demo_v3_rviz.py
```

### 2. RViz 없이 실행
```bash
python3 demo_v3_rviz.py --no-rviz
```

### 3. 수동 RViz 실행
```bash
# 프로그램 먼저 실행
python3 demo_v3_rviz.py

# 별도 터미널에서 RViz
rviz -d piper.rviz
```

## 📦 필요한 ROS 패키지

### 필수 패키지
```bash
sudo apt-get install ros-noetic-rviz
sudo apt-get install ros-noetic-robot-state-publisher
sudo apt-get install ros-noetic-joint-state-publisher
sudo apt-get install ros-noetic-tf
```

### URDF 모델 (선택사항)
PIPER 로봇의 3D 모델이 있다면 더 정확한 시각화가 가능합니다.

```bash
# piper_description 패키지 구조
~/catkin_ws/src/piper_description/
├── urdf/
│   └── piper.urdf.xacro
├── meshes/
│   ├── link1.stl
│   ├── link2.stl
│   └── ...
├── rviz/
│   └── piper.rviz
└── launch/
    └── display.launch
```

## 🔧 ROS Topics

### Published Topics

#### /joint_states
```yaml
Type: sensor_msgs/JointState
Rate: ~20Hz
Content:
  - joint_1 ~ joint_6 (관절 각도)
  - gripper_joint (그리퍼 위치)
```

**예시:**
```python
header:
  stamp: {secs: 1699354789, nsecs: 123456789}
name: ['joint_1', 'joint_2', 'joint_3', 'joint_4', 'joint_5', 'joint_6', 'gripper_joint']
position: [0.0, 0.523, -1.047, 0.0, 0.523, 0.0, 0.05]
velocity: []
effort: []
```

#### /tf
```yaml
Type: geometry_msgs/TransformStamped
Rate: ~20Hz
Transforms:
  - world → base_link (static)
  - base_link → end_effector (dynamic)
```

**예시:**
```python
transforms:
  - header:
      stamp: {secs: 1699354789, nsecs: 123456789}
      frame_id: "base_link"
    child_frame_id: "end_effector"
    transform:
      translation: {x: 0.35, y: 0.0, z: 0.3}
      rotation: {x: 0.0, y: 1.0, z: 0.0, w: 0.0}
```

## 🎨 RViz 설정

### Display 패널 구성

#### 1. Grid
- **목적:** 바닥 그리드
- **설정:**
  - Cell Size: 0.1m
  - Plane: XY
  - Reference Frame: world

#### 2. RobotModel
- **목적:** 로봇 3D 모델
- **설정:**
  - Robot Description: robot_description
  - Visual Enabled: true
  - Collision Enabled: false

#### 3. TF
- **목적:** 좌표계 표시
- **설정:**
  - Show Arrows: true
  - Show Axes: true
  - Marker Scale: 0.3

#### 4. Axes
- **목적:** 기준점 표시
- **Base Link:**
  - Length: 0.2m
  - Radius: 0.02m
- **End Effector:**
  - Length: 0.1m
  - Radius: 0.01m

### View 설정

#### Orbit Camera (권장)
```yaml
Class: rviz/Orbit
Distance: 1.5
Focal Point: {X: 0.3, Y: 0.0, Z: 0.3}
Pitch: 0.5
Yaw: 0.785
```

## 📊 데이터 흐름

```
PIPER Robot
    ↓
GetArmJointMsgs()
GetArmEndPoseMsgs()
    ↓
demo_v3_rviz.py
    ↓
publish_robot_state()
    ↓
┌─────────────────┬─────────────────┐
│  /joint_states  │      /tf        │
└────────┬────────┴────────┬────────┘
         ↓                 ↓
  robot_state_      tf_broadcaster
     publisher
         ↓                 ↓
         └────────┬────────┘
                  ↓
               RViz
```

## 🔍 문제 해결

### Q: RViz에 로봇이 안 보여요
**A:** 순서대로 확인:
```bash
# 1. ROS core 실행 확인
rosnode list

# 2. Topic 확인
rostopic list
rostopic echo /joint_states

# 3. TF 확인
rosrun tf view_frames
evince frames.pdf

# 4. RobotModel 설정 확인
# RViz Display 패널에서:
# - RobotModel → Robot Description: robot_description
# - Status가 "Error"가 아닌지 확인
```

### Q: "No transform from..." 오류
**A:** TF 트리 확인
```bash
# TF 트리 시각화
rosrun rqt_tf_tree rqt_tf_tree

# world → base_link transform 확인
rosrun tf tf_echo world base_link

# 문제 해결:
# static_transform_publisher가 실행 중인지 확인
# launch 파일에서 world → base_link 정의 확인
```

### Q: Joint states가 업데이트 안 돼요
**A:** 프로그램 상태 확인
```bash
# Topic Hz 확인
rostopic hz /joint_states

# 출력 예상: average rate: 20.000

# 만약 0 Hz라면:
# 1. demo_v3_rviz.py가 실행 중인지 확인
# 2. --no-rviz 옵션 없이 실행했는지 확인
# 3. ROS_AVAILABLE = True인지 코드에서 확인
```

### Q: URDF가 없어서 로봇이 안 보여요
**A:** 간단한 URDF 작성
```xml
<!-- piper_simple.urdf -->
<?xml version="1.0"?>
<robot name="piper">
  <link name="base_link">
    <visual>
      <geometry>
        <box size="0.1 0.1 0.1"/>
      </geometry>
      <material name="blue">
        <color rgba="0 0 1 1"/>
      </material>
    </visual>
  </link>
  
  <link name="link1">
    <visual>
      <geometry>
        <cylinder length="0.2" radius="0.03"/>
      </geometry>
    </visual>
  </link>
  
  <joint name="joint_1" type="revolute">
    <parent link="base_link"/>
    <child link="link1"/>
    <axis xyz="0 0 1"/>
    <limit lower="-3.14" upper="3.14" effort="100" velocity="1.0"/>
  </joint>
  
  <!-- 나머지 링크와 조인트... -->
</robot>
```

### Q: RViz가 느려요
**A:** 설정 최적화
```yaml
# RViz 설정에서:
Frame Rate: 15  # 30 → 15

# RobotModel:
Update Interval: 0.1  # 0 → 0.1

# TF:
Frame Timeout: 30  # 15 → 30
```

## 💡 활용 팁

### 1. 궤적 기록
```bash
# 터미널에서:
rosbag record -a

# 나중에 재생:
rosbag play your_bag.bag
```

### 2. 스크린샷
```
RViz 메뉴: File → Save Image
또는: Ctrl + S
```

### 3. 시점 저장
```
Views 패널에서:
Current View → 우클릭 → Add View
나중에 저장된 시점으로 전환 가능
```

### 4. Display 추가
```yaml
# 추가 가능한 Display들:
- Path: 로봇 경로 표시
- Marker: 커스텀 마커
- PointCloud2: 포인트 클라우드
- Image: 카메라 이미지
```

### 5. 실시간 Joint 값 확인
```bash
# 터미널에서 실시간 모니터링:
rostopic echo /joint_states

# 또는 rqt 사용:
rqt_plot /joint_states/position[0]:position[1]:position[2]
```

## 🎓 고급 기능

### 1. 커스텀 마커 추가
```python
from visualization_msgs.msg import Marker

def publish_target_marker(self, position):
    """목표 위치 마커 표시"""
    marker = Marker()
    marker.header.frame_id = "world"
    marker.header.stamp = rospy.Time.now()
    marker.type = Marker.SPHERE
    marker.action = Marker.ADD
    marker.pose.position.x = position[0]
    marker.pose.position.y = position[1]
    marker.pose.position.z = position[2]
    marker.scale.x = 0.05
    marker.scale.y = 0.05
    marker.scale.z = 0.05
    marker.color.r = 1.0
    marker.color.a = 1.0
    
    self.marker_pub.publish(marker)
```

### 2. 궤적 표시
```python
from nav_msgs.msg import Path
from geometry_msgs.msg import PoseStamped

def publish_trajectory(self, positions):
    """로봇 궤적 표시"""
    path = Path()
    path.header.frame_id = "world"
    path.header.stamp = rospy.Time.now()
    
    for pos in positions:
        pose = PoseStamped()
        pose.header = path.header
        pose.pose.position.x = pos[0]
        pose.pose.position.y = pos[1]
        pose.pose.position.z = pos[2]
        path.poses.append(pose)
    
    self.path_pub.publish(path)
```

### 3. Interactive Markers
```python
from interactive_markers.interactive_marker_server import *
from visualization_msgs.msg import InteractiveMarker

def create_interactive_marker(self):
    """인터랙티브 마커 (드래그 가능)"""
    server = InteractiveMarkerServer("piper_target")
    
    int_marker = InteractiveMarker()
    int_marker.header.frame_id = "world"
    int_marker.name = "target_position"
    int_marker.description = "Target"
    
    # 마커 설정...
    server.insert(int_marker, self.process_feedback)
    server.applyChanges()
```

## 📚 참고 자료

### ROS Wiki
- [RViz User Guide](http://wiki.ros.org/rviz/UserGuide)
- [robot_state_publisher](http://wiki.ros.org/robot_state_publisher)
- [tf Tutorial](http://wiki.ros.org/tf/Tutorials)

### URDF 튜토리얼
- [Building a Visual Robot Model](http://wiki.ros.org/urdf/Tutorials/Building%20a%20Visual%20Robot%20Model%20with%20URDF%20from%20Scratch)
- [URDF XML Specification](http://wiki.ros.org/urdf/XML)

## 🎬 데모 시나리오

### 1. 기본 시각화
```bash
# 1. ROS 시작
roscore &

# 2. RViz 실행
roslaunch piper_rviz.launch &

# 3. 프로그램 실행
python3 demo_v3_rviz.py

# 4. 캘리브레이션 (C)
# 5. 제어 시작 (SPACE)
# 6. RViz에서 실시간 로봇 움직임 확인
```

### 2. 기록 및 재생
```bash
# 1. 기록
rosbag record /joint_states /tf

# 2. 작업 수행
# ...

# 3. Ctrl+C로 기록 종료

# 4. 재생
rosbag play *.bag

# RViz에서 기록된 동작 재생됨
```

## ✅ 체크리스트

### 시작 전
- [ ] ROS 설치 확인 (`roscore` 실행)
- [ ] 필요한 패키지 설치
- [ ] launch 파일 경로 확인
- [ ] URDF 파일 (선택사항)

### 실행 중
- [ ] `/joint_states` topic 확인
- [ ] `/tf` topic 확인
- [ ] RViz에서 로봇 표시 확인
- [ ] 실시간 업데이트 확인

### 문제 발생 시
- [ ] `rostopic list` 확인
- [ ] `rosnode list` 확인
- [ ] RViz Display Status 확인
- [ ] 터미널 오류 메시지 확인

---

**🎨 RViz로 로봇을 3D로 시각화하세요!**

**버전:** v3.0  
**작성일:** 2025-11-06  
**작성자:** Claude

즐거운 시각화 되세요! 📊🤖✨
