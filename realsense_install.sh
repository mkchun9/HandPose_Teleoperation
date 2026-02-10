#!/bin/bash

# PIPER + RealSense D435I 손동작 텔레오퍼레이션 설치 스크립트

set -e

echo "============================================================"
echo "  PIPER + Intel RealSense D435I 텔레오퍼레이션 설치"
echo "============================================================"
echo ""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 1. 시스템 업데이트
echo -e "${YELLOW}[1/7] 시스템 패키지 업데이트...${NC}"
sudo apt-get update

# 2. 필수 패키지 설치
echo -e "${YELLOW}[2/7] 필수 시스템 패키지 설치...${NC}"
sudo apt-get install -y \
    python3-pip \
    python3-opencv \
    libopencv-dev \
    git \
    wget \
    ros-noetic-ros-base \
    ros-noetic-geometry-msgs \
    ros-noetic-std-msgs

# 3. Intel RealSense SDK 설치
echo -e "${YELLOW}[3/7] Intel RealSense SDK 설치...${NC}"

# RealSense 저장소 등록
if [ ! -f /etc/apt/sources.list.d/realsense-public.list ]; then
    sudo mkdir -p /etc/apt/keyrings
    curl -sSf https://librealsense.intel.com/Debian/librealsense.pgp | sudo tee /etc/apt/keyrings/librealsense.pgp > /dev/null
    
    echo "deb [signed-by=/etc/apt/keyrings/librealsense.pgp] https://librealsense.intel.com/Debian/apt-repo $(lsb_release -cs) main" | \
    sudo tee /etc/apt/sources.list.d/realsense-public.list
    
    sudo apt-get update
fi

# RealSense 라이브러리 설치
sudo apt-get install -y \
    librealsense2-dkms \
    librealsense2-utils \
    librealsense2-dev \
    librealsense2-dbg

echo -e "${GREEN}✓ RealSense SDK 설치 완료${NC}"

# 4. RealSense 연결 확인
echo -e "${YELLOW}[4/7] RealSense 카메라 확인...${NC}"
if command -v realsense-viewer &> /dev/null; then
    echo -e "${GREEN}✓ RealSense Viewer 설치됨${NC}"
    echo -e "${BLUE}  카메라를 연결한 후 'realsense-viewer' 명령으로 테스트하세요${NC}"
else
    echo -e "${RED}✗ RealSense Viewer를 찾을 수 없습니다${NC}"
fi

# 5. Python 패키지 설치
echo -e "${YELLOW}[5/7] Python 패키지 설치...${NC}"
pip3 install --upgrade pip
pip3 install -r requirements_realsense.txt

# pyrealsense2 추가 설치 확인
if python3 -c "import pyrealsense2" 2>/dev/null; then
    echo -e "${GREEN}✓ pyrealsense2 설치 완료${NC}"
else
    echo -e "${YELLOW}! pyrealsense2 설치 재시도...${NC}"
    pip3 install pyrealsense2 --upgrade
fi

# 6. PIPER SDK 설치
echo -e "${YELLOW}[6/7] PIPER SDK 확인...${NC}"
if python3 -c "import piper_sdk" 2>/dev/null; then
    echo -e "${GREEN}✓ PIPER SDK가 이미 설치되어 있습니다${NC}"
else
    echo -e "${YELLOW}PIPER SDK를 설치하시겠습니까? (y/n)${NC}"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        if [ ! -d "piper_sdk" ]; then
            git clone https://github.com/agilexrobotics/piper_sdk.git
        fi
        cd piper_sdk
        pip3 install -e .
        cd ..
        echo -e "${GREEN}✓ PIPER SDK 설치 완료${NC}"
    else
        echo -e "${YELLOW}! PIPER SDK 설치를 건너뛰었습니다. 시뮬레이션 모드로 실행됩니다.${NC}"
    fi
fi

# 7. 실행 권한 부여
echo -e "${YELLOW}[7/7] 실행 권한 설정...${NC}"
chmod +x realsense_teleoperation.py
chmod +x student_experience.py
chmod +x piper_controller.py

# USB 권한 설정
echo -e "${YELLOW}USB 권한 설정...${NC}"
sudo usermod -a -G video $USER

# RealSense USB 규칙 설정
sudo bash -c 'cat > /etc/udev/rules.d/99-realsense-libusb.rules << EOF
# Intel RealSense D400 Series
SUBSYSTEMS=="usb", ATTRS{idVendor}=="8086", ATTRS{idProduct}=="0b07", MODE:="0666", GROUP:="plugdev"
SUBSYSTEMS=="usb", ATTRS{idVendor}=="8086", ATTRS{idProduct}=="0b3a", MODE:="0666", GROUP:="plugdev"
SUBSYSTEMS=="usb", ATTRS{idVendor}=="8086", ATTRS{idProduct}=="0ad1", MODE:="0666", GROUP:="plugdev"
SUBSYSTEMS=="usb", ATTRS{idVendor}=="8086", ATTRS{idProduct}=="0ad2", MODE:="0666", GROUP:="plugdev"
SUBSYSTEMS=="usb", ATTRS{idVendor}=="8086", ATTRS{idProduct}=="0ad3", MODE:="0666", GROUP:="plugdev"
SUBSYSTEMS=="usb", ATTRS{idVendor}=="8086", ATTRS{idProduct}=="0ad4", MODE:="0666", GROUP:="plugdev"
SUBSYSTEMS=="usb", ATTRS{idVendor}=="8086", ATTRS{idProduct}=="0ad5", MODE:="0666", GROUP:="plugdev"
EOF'

sudo udevadm control --reload-rules
sudo udevadm trigger

# 완료
echo ""
echo "============================================================"
echo -e "${GREEN}✓ 설치가 완료되었습니다!${NC}"
echo "============================================================"
echo ""
echo "🎯 다음 명령어로 프로그램을 실행하세요:"
echo ""
echo "  기본 텔레오퍼레이션:"
echo "    python3 realsense_teleoperation.py"
echo ""
echo "  중학생 체험 프로그램 (추천!):"
echo "    python3 student_experience.py"
echo ""
echo "============================================================"
echo ""
echo -e "${BLUE}📷 RealSense 카메라 테스트:${NC}"
echo "    realsense-viewer"
echo ""
echo -e "${YELLOW}⚠️  중요: USB 권한 변경을 적용하려면${NC}"
echo -e "${YELLOW}   로그아웃 후 다시 로그인하세요!${NC}"
echo ""