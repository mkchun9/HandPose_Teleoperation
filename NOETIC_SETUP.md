# 🚀 ROS Noetic (Ubuntu 20.04) 설치 및 실행 가이드

## 📋 시스템 요구사항

- **OS:** Ubuntu 20.04 Focal Fossa
- **ROS:** Noetic Ninjemys
- **Python:** 3.8+ (Noetic는 Python 3 전용)

## 🔧 ROS Noetic 설치

### 1. ROS Noetic 설치 (아직 안 했다면)

```bash
# 1.1 소스 추가
sudo sh -c 'echo "deb http://packages.ros.org/ros/ubuntu $(lsb_release -sc) main" > /etc/apt/sources.list.d/ros-latest.list'

# 1.2 키 추가
sudo apt install curl
curl -s https://raw.githubusercontent.com/ros/rosdistro/master/ros.asc | sudo apt-key add -

# 1.3 패키지 업데이트
sudo apt update

# 1.4 ROS Noetic Desktop Full 설치 (권장)
sudo apt install ros-noetic-desktop-full

# 또는 Base만 설치 (더 가볍게)
# sudo apt install ros-noetic-ros-base
```

### 2. 환경 설정

```bash
# 2.1 bashrc에 자동 source 추가
echo "source /opt/ros/noetic/setup.bash" >> ~/.bashrc
source ~/.bashrc

# 2.2 확인
rosversion -d
# 출력: noetic
```

### 3. 필수 도구 설치

```bash
# rosdep 초기화
sudo apt install python3-rosdep
sudo rosdep init
rosdep update

# catkin 빌드 도구
sudo apt install python3-catkin-tools

# ROS 빌드 도구
sudo apt install python3-rosinstall python3-rosinstall-generator python3-wstool build-essential
```

## 📦 PIPER 시각화 패키지 설치

### 필수 ROS 패키지

```bash
# RViz 및 관련 패키지
sudo apt-get install ros-noetic-rviz

# Robot state publisher
sudo apt-get install ros-noetic-robot-state-publisher

# Joint state publisher (GUI 포함)
sudo apt-get install ros-noetic-joint-state-publisher
sudo apt-get install ros-noetic-joint-state-publisher-gui

# TF2 (Noetic 권장)
sudo apt-get install ros-noetic-tf2-ros
sudo apt-get install ros-noetic-tf2-tools
sudo apt-get install ros-noetic-tf-conversions

# URDF 도구 (선택사항)
sudo apt-get install ros-noetic-urdf
sudo apt-get install ros-noetic-xacro

# 시각화 도구
sudo apt-get install ros-noetic-rqt
sudo apt-get install ros-noetic-rqt-common-plugins
sudo apt-get install ros-noetic-rqt-tf-tree
```

### Python 의존성 (Python 3)

```bash
# ROS Python 3 패키지
pip3 install rospkg

# 이미 설치되어 있을 다른 패키지들
pip3 install opencv-python
pip3 install numpy
pip3 install pyrealsense2
pip3 install mediapipe
```

## 🎯 빠른 시작

### 방법 1: 간단한 실행 (URDF 없이)

```bash
# 터미널 1: ROS Master
roscore

# 터미널 2: RViz
roslaunch piper_simple.launch
# 또는 직접:
# rviz -d piper.rviz

# 터미널 3: 프로그램
python3 demo_v3_rviz.py
```

### 방법 2: 모든 기능 활성화 (한 줄에)

```bash
# ROS Master가 이미 실행 중이라면:
python3 demo_v3_rviz.py & roslaunch piper_simple.launch
```

### 방법 3: RViz 없이 실행

```bash
python3 demo_v3_safe.py
# 또는
python3 demo_v3_rviz.py --no-rviz
```

## 📊 ROS Topics 확인

### 발행되는 Topics 확인

```bash
# Topic 리스트
rostopic list

# 예상 출력:
# /joint_states
# /rosout
# /rosout_agg
# /tf
# /tf_static
```

### Joint States 확인

```bash
# 실시간 데이터 확인
rostopic echo /joint_states

# 주파수 확인
rostopic hz /joint_states
# 예상 출력: average rate: ~20.000

# 정보 확인
rostopic info /joint_states
```

### TF 확인

```bash
# TF 트리 시각화
rosrun rqt_tf_tree rqt_tf_tree

# 또는
rosrun tf2_tools view_frames.py
# PDF 생성됨
evince frames.pdf

# 특정 TF 확인
rosrun tf tf_echo world base_link
rosrun tf tf_echo base_link end_effector
```

## 🔍 문제 해결

### Q: "Unable to contact ROS master" 오류

```bash
# ROS Master 확인
ps aux | grep roscore

# 실행 안 되어 있으면:
roscore &

# ROS_MASTER_URI 확인
echo $ROS_MASTER_URI
# 출력: http://localhost:11311
```

### Q: "No module named 'rospy'" 오류

```bash
# ROS 환경 설정 확인
source /opt/ros/noetic/setup.bash

# Python 3로 실행하는지 확인
python3 --version  # Python 3.8+
python3 demo_v3_rviz.py  # python이 아닌 python3 사용!
```

### Q: "package 'piper_description' not found" 오류

```bash
# launch 파일 수정:
# piper_simple.launch 사용 (URDF 불필요)
roslaunch piper_simple.launch

# 또는 직접 RViz 실행:
rviz -d piper.rviz
```

### Q: TF transform 오류

```bash
# Static TF가 발행되고 있는지 확인
rostopic echo /tf_static

# demo_v3_rviz.py가 실행 중인지 확인
# (static TF를 프로그램에서 발행)

# 수동으로 static TF 발행:
rosrun tf2_ros static_transform_publisher 0 0 0 0 0 0 world base_link
```

### Q: RViz에 아무것도 안 보임

```bash
# 1. Fixed Frame 확인
# RViz에서: Displays → Global Options → Fixed Frame = "world"

# 2. TF 활성화 확인
# Displays → TF → Enabled ✓

# 3. Axes 추가
# Add → Axes
# Reference Frame: base_link

# 4. Topic 확인
rostopic list
rostopic hz /joint_states
```

## 🎓 ROS Noetic 특징 (vs Melodic)

| 항목 | Melodic | Noetic |
|------|---------|--------|
| Ubuntu | 18.04 | **20.04** |
| Python | 2.7 | **3.8+** |
| tf | tf (old) | **tf2 권장** |
| EOL | 2023년 5월 | 2025년 5월 |

### Noetic 마이그레이션 체크리스트

- ✅ Python 3 사용 (`python3` 명령어)
- ✅ `tf2_ros` 사용 (tf 대신)
- ✅ `TransformStamped` 메시지 구조
- ✅ `static_transform_publisher` → 코드에서 직접 발행
- ✅ `print()` 함수 (Python 3)

## 💡 유용한 도구

### 1. RQt 도구

```bash
# RQt 메인 창
rqt

# 또는 개별 플러그인:
rqt_graph        # 노드 그래프
rqt_plot         # 데이터 플롯
rqt_console      # 로그 콘솔
rqt_bag          # rosbag 재생
```

### 2. TF 도구

```bash
# TF 트리 보기
rosrun rqt_tf_tree rqt_tf_tree

# TF 정보 출력
rosrun tf2_tools view_frames.py

# TF 모니터
rosrun tf tf_monitor
```

### 3. 데이터 기록/재생

```bash
# 모든 topic 기록
rosbag record -a

# 특정 topic만 기록
rosbag record /joint_states /tf

# 재생
rosbag play your_bag.bag

# 정보 확인
rosbag info your_bag.bag
```

## 🚀 고급 설정

### Catkin Workspace 생성 (URDF 개발용)

```bash
# 1. 작업 공간 생성
mkdir -p ~/catkin_ws/src
cd ~/catkin_ws/
catkin_make

# 2. Source
source devel/setup.bash
echo "source ~/catkin_ws/devel/setup.bash" >> ~/.bashrc

# 3. 패키지 생성
cd ~/catkin_ws/src
catkin_create_pkg piper_description rospy rviz urdf

# 4. 디렉토리 구조
cd piper_description
mkdir urdf meshes rviz launch

# 5. 파일 복사
cp /path/to/piper.rviz rviz/
cp /path/to/piper_simple.launch launch/

# 6. 빌드
cd ~/catkin_ws
catkin_make

# 7. 실행
roslaunch piper_description piper_simple.launch
```

### 네트워크 설정 (다른 컴퓨터에서 RViz)

```bash
# Master 컴퓨터 (로봇 제어):
export ROS_MASTER_URI=http://192.168.1.100:11311
export ROS_IP=192.168.1.100

# Client 컴퓨터 (RViz):
export ROS_MASTER_URI=http://192.168.1.100:11311
export ROS_IP=192.168.1.101

# 확인
echo $ROS_MASTER_URI
echo $ROS_IP
```

## 📚 참고 자료

### 공식 문서
- [ROS Noetic 설치](http://wiki.ros.org/noetic/Installation/Ubuntu)
- [ROS Tutorials](http://wiki.ros.org/ROS/Tutorials)
- [TF2 Tutorials](http://wiki.ros.org/tf2/Tutorials)
- [RViz User Guide](http://wiki.ros.org/rviz/UserGuide)

### Python 3 마이그레이션
- [Python 3 in ROS Noetic](http://wiki.ros.org/UsingPython3)
- [rospy Python 3](http://wiki.ros.org/rospy)

## ✅ 설치 확인 체크리스트

### 기본 설치 확인
```bash
# ROS 버전
rosversion -d
# 출력: noetic

# Python 버전
python3 --version
# 출력: Python 3.8.x

# ROS 패키지 확인
rospack list | grep rviz
rospack list | grep tf2

# ROS 환경 변수
env | grep ROS
# ROS_VERSION=1
# ROS_PYTHON_VERSION=3
# ROS_DISTRO=noetic
```

### 실행 테스트
```bash
# 1. ROS Master
roscore &
sleep 2

# 2. RViz 테스트
rviz &
sleep 3
killall rviz

# 3. Topic 테스트
rostopic list

# 4. TF 테스트
rosrun tf2_ros static_transform_publisher 0 0 0 0 0 0 world test
rostopic echo /tf_static

# 모두 성공하면 준비 완료! ✅
```

## 🎯 최종 실행 (요약)

```bash
# === 간단한 3단계 ===

# 1단계: ROS 시작
roscore &

# 2단계: 프로그램 + RViz 동시 실행
python3 demo_v3_rviz.py &
sleep 2
roslaunch piper_simple.launch

# 3단계: 손으로 제어!
# [C] - 캘리브레이션
# [SPACE] - 제어 시작
# [H] - 홈으로
# [Q] - 종료
```

## 🎉 성공 확인

프로그램이 제대로 작동하면 다음과 같은 메시지가 출력됩니다:

```
✅ ROS Noetic 모듈 로드 성공
✅ ROS Noetic 초기화 완료
📊 RViz 시각화 활성화
   터미널에서 실행: roslaunch piper_simple.launch
   또는: rviz -d piper.rviz
```

그리고 RViz에서:
- ✅ TF axes 표시 (world, base_link, end_effector)
- ✅ Joint states 업데이트 (~20Hz)
- ✅ End effector 위치 실시간 변화

---

**🚀 ROS Noetic + PIPER를 즐기세요!**

**버전:** v3.0 Noetic  
**작성일:** 2025-11-06  
**작성자:** Claude

Happy ROSing! 🤖✨
