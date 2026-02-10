#!/bin/bash
# PIPER ROS Noetic 자동 설치 스크립트
# Ubuntu 20.04 + ROS Noetic

set -e  # 오류 시 중단

echo "=========================================="
echo "  PIPER ROS Noetic 패키지 설치 스크립트"
echo "  Ubuntu 20.04 + ROS Noetic"
echo "=========================================="
echo ""

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ROS 확인
echo -e "${YELLOW}[1/5] ROS Noetic 확인 중...${NC}"
if [ -f "/opt/ros/noetic/setup.bash" ]; then
    echo -e "${GREEN}✅ ROS Noetic 설치됨${NC}"
    source /opt/ros/noetic/setup.bash
else
    echo -e "${RED}❌ ROS Noetic이 설치되지 않았습니다${NC}"
    echo "다음 명령어로 설치하세요:"
    echo "  sudo apt install ros-noetic-desktop-full"
    exit 1
fi

# 패키지 업데이트
echo ""
echo -e "${YELLOW}[2/5] 패키지 목록 업데이트 중...${NC}"
sudo apt-get update

# 필수 ROS 패키지 설치
echo ""
echo -e "${YELLOW}[3/5] ROS 패키지 설치 중...${NC}"

PACKAGES=(
    "ros-noetic-rviz"
    "ros-noetic-robot-state-publisher"
    "ros-noetic-joint-state-publisher"
    "ros-noetic-joint-state-publisher-gui"
    "ros-noetic-tf2-ros"
    "ros-noetic-tf2-tools"
    "ros-noetic-tf-conversions"
    "ros-noetic-rqt"
    "ros-noetic-rqt-common-plugins"
    "ros-noetic-rqt-tf-tree"
)

echo "설치할 패키지: ${#PACKAGES[@]}개"

for package in "${PACKAGES[@]}"; do
    echo -ne "  설치 중: $package ... "
    if sudo apt-get install -y $package > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${RED}✗${NC}"
    fi
done

# 선택적 패키지
echo ""
echo -e "${YELLOW}[4/5] 선택적 패키지 설치 중...${NC}"

OPTIONAL_PACKAGES=(
    "ros-noetic-urdf"
    "ros-noetic-xacro"
)

for package in "${OPTIONAL_PACKAGES[@]}"; do
    echo -ne "  설치 중: $package ... "
    if sudo apt-get install -y $package > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${YELLOW}⚠ (선택사항)${NC}"
    fi
done

# Python 패키지
echo ""
echo -e "${YELLOW}[5/5] Python 패키지 확인 중...${NC}"

# rospkg 확인
echo -ne "  확인 중: rospkg ... "
if python3 -c "import rospkg" 2>/dev/null; then
    echo -e "${GREEN}✓${NC}"
else
    echo -ne "${YELLOW}설치 중...${NC}"
    pip3 install rospkg > /dev/null 2>&1
    echo -e "${GREEN}✓${NC}"
fi

# numpy 확인
echo -ne "  확인 중: numpy ... "
if python3 -c "import numpy" 2>/dev/null; then
    echo -e "${GREEN}✓${NC}"
else
    echo -ne "${YELLOW}설치 중...${NC}"
    pip3 install numpy > /dev/null 2>&1
    echo -e "${GREEN}✓${NC}"
fi

# 환경 변수 설정 확인
echo ""
echo -e "${YELLOW}환경 변수 확인 중...${NC}"
if grep -q "source /opt/ros/noetic/setup.bash" ~/.bashrc; then
    echo -e "${GREEN}✅ .bashrc에 ROS 설정 있음${NC}"
else
    echo -e "${YELLOW}⚠️  .bashrc에 ROS 설정 추가 중...${NC}"
    echo "" >> ~/.bashrc
    echo "# ROS Noetic" >> ~/.bashrc
    echo "source /opt/ros/noetic/setup.bash" >> ~/.bashrc
    echo -e "${GREEN}✅ 추가 완료${NC}"
    echo -e "${YELLOW}다음 명령어를 실행하거나 새 터미널을 여세요:${NC}"
    echo "  source ~/.bashrc"
fi

# 설치 확인
echo ""
echo "=========================================="
echo "  설치 확인"
echo "=========================================="

# ROS 버전
echo -n "ROS 버전: "
rosversion -d 2>/dev/null || echo "확인 실패"

# Python 버전
echo -n "Python 버전: "
python3 --version

# RViz 확인
echo -n "RViz: "
if command -v rviz &> /dev/null; then
    echo -e "${GREEN}설치됨${NC}"
else
    echo -e "${RED}없음${NC}"
fi

# TF2 확인
echo -n "TF2: "
if rospack find tf2_ros &> /dev/null; then
    echo -e "${GREEN}설치됨${NC}"
else
    echo -e "${RED}없음${NC}"
fi

# 완료
echo ""
echo "=========================================="
echo -e "${GREEN}✅ 설치 완료!${NC}"
echo "=========================================="
echo ""
echo "다음 명령어로 실행하세요:"
echo ""
echo "  # 터미널 1: ROS Master"
echo "  roscore"
echo ""
echo "  # 터미널 2: RViz"
echo "  roslaunch piper_simple.launch"
echo ""
echo "  # 터미널 3: 프로그램"
echo "  python3 demo_v3_rviz.py"
echo ""
echo "또는 간단하게:"
echo "  roscore &"
echo "  python3 demo_v3_rviz.py &"
echo "  roslaunch piper_simple.launch"
echo ""
echo -e "${YELLOW}※ 새 터미널을 열거나 다음을 실행하세요:${NC}"
echo "  source ~/.bashrc"
echo ""
