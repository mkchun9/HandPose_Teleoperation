#!/bin/bash
# RealSense D435i 빠른 수정 스크립트

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=========================================="
echo "  RealSense D435i 빠른 수정 스크립트"
echo "=========================================="
echo ""

# 1. USB 확인
echo -e "${YELLOW}[1/7] USB 연결 확인...${NC}"
if lsusb | grep -q "Intel"; then
    echo -e "${GREEN}✅ Intel 디바이스 발견${NC}"
    lsusb | grep Intel
else
    echo -e "${RED}❌ Intel 디바이스 없음${NC}"
    echo "USB 케이블을 확인하고 다시 연결하세요"
    exit 1
fi
echo ""

# # 2. 권한 확인 및 추가
# echo -e "${YELLOW}[2/7] 권한 확인...${NC}"
# if groups | grep -q "video" && groups | grep -q "plugdev"; then
#     echo -e "${GREEN}✅ 권한 있음${NC}"
# else
#     echo -e "${YELLOW}⚠️  권한 추가 중...${NC}"
#     sudo usermod -aG video $USER
#     sudo usermod -aG plugdev $USER
#     echo -e "${GREEN}✅ 권한 추가됨 (재로그인 필요)${NC}"
# fi
# echo ""

# 3. librealsense2 확인
echo -e "${YELLOW}[3/7] librealsense2 확인...${NC}"
if dpkg -l | grep -q "librealsense2"; then
    echo -e "${GREEN}✅ librealsense2 설치됨${NC}"
else
    echo -e "${YELLOW}⚠️  librealsense2 설치 중...${NC}"
    
    # 키 추가
    sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-key F6E65AC044F831AC80A06380C8B3A55A6F3EFCDE || true
    
    # 저장소 추가
    sudo add-apt-repository "deb https://librealsense.intel.com/Debian/apt-repo $(lsb_release -cs) main" -u
    
    # 설치
    sudo apt update
    sudo apt install -y librealsense2-dkms librealsense2-utils librealsense2-dev
    
    echo -e "${GREEN}✅ librealsense2 설치 완료${NC}"
fi
echo ""

# 4. pyrealsense2 확인
echo -e "${YELLOW}[4/7] pyrealsense2 확인...${NC}"
if python3 -c "import pyrealsense2" 2>/dev/null; then
    echo -e "${GREEN}✅ pyrealsense2 설치됨${NC}"
    VERSION=$(python3 -c "import pyrealsense2 as rs; print(rs.__version__)" 2>/dev/null || echo "unknown")
    echo "   버전: $VERSION"
else
    echo -e "${YELLOW}⚠️  pyrealsense2 설치 중...${NC}"
    pip3 install pyrealsense2 --upgrade
    echo -e "${GREEN}✅ pyrealsense2 설치 완료${NC}"
fi
echo ""

# 5. udev rules 확인
echo -e "${YELLOW}[5/7] udev rules 확인...${NC}"
if [ -f "/etc/udev/rules.d/99-realsense-libusb.rules" ]; then
    echo -e "${GREEN}✅ udev rules 있음${NC}"
else
    echo -e "${YELLOW}⚠️  udev rules 생성 중...${NC}"
    
    sudo tee /etc/udev/rules.d/99-realsense-libusb.rules > /dev/null << 'EOF'
# Intel RealSense D400 Series
SUBSYSTEMS=="usb", ATTRS{idVendor}=="8086", ATTRS{idProduct}=="0b3a", MODE="0666", GROUP="plugdev"
SUBSYSTEMS=="usb", ATTRS{idVendor}=="8086", ATTRS{idProduct}=="0b37", MODE="0666", GROUP="plugdev"
SUBSYSTEMS=="usb", ATTRS{idVendor}=="8086", MODE="0666", GROUP="plugdev"
EOF
    
    sudo udevadm control --reload-rules
    sudo udevadm trigger
    
    echo -e "${GREEN}✅ udev rules 생성 완료${NC}"
fi
echo ""

# 6. /dev/video 권한 확인
echo -e "${YELLOW}[6/7] 디바이스 권한 확인...${NC}"
if ls /dev/video* 2>/dev/null; then
    echo -e "${GREEN}✅ 비디오 디바이스 있음${NC}"
    ls -la /dev/video* | head -3
    
    # 임시 권한 부여 (재부팅 시 초기화됨)
    echo -e "${YELLOW}⚠️  임시 권한 부여 중...${NC}"
    sudo chmod 666 /dev/video* 2>/dev/null || true
    echo -e "${GREEN}✅ 권한 부여 완료${NC}"
else
    echo -e "${YELLOW}⚠️  비디오 디바이스 없음 (카메라 재연결 필요)${NC}"
fi
echo ""

# 7. 카메라 테스트
echo -e "${YELLOW}[7/7] 카메라 테스트...${NC}"
if python3 -c "import pyrealsense2 as rs; ctx = rs.context(); devs = ctx.query_devices(); print(f'발견: {len(devs)}개'); exit(0 if len(devs) > 0 else 1)" 2>/dev/null; then
    echo -e "${GREEN}✅ 카메라 인식됨!${NC}"
    python3 -c "import pyrealsense2 as rs; ctx = rs.context(); [print(f'  - {dev.get_info(rs.camera_info.name)}') for dev in ctx.query_devices()]" 2>/dev/null
else
    echo -e "${RED}❌ 카메라 인식 실패${NC}"
    echo ""
    echo "추가 조치:"
    echo "1. USB 케이블을 뽑았다가 다시 연결"
    echo "2. 다른 USB 3.0 포트 시도"
    echo "3. 재부팅 후 다시 테스트"
    echo ""
    exit 1
fi
echo ""

# 완료
echo "=========================================="
echo -e "${GREEN}✅ 수정 완료!${NC}"
echo "=========================================="
echo ""
echo "다음 단계:"
echo "1. 권한 그룹에 추가되었다면 재로그인 필요"
echo "   (로그아웃 후 다시 로그인)"
echo ""
echo "2. 카메라 테스트:"
echo "   python3 test_realsense.py"
echo ""
echo "3. 프로그램 실행:"
echo "   python3 demo_v3_rviz.py"
echo ""

# 재로그인 필요 여부
if ! groups | grep -q "video" || ! groups | grep -q "plugdev"; then
    echo -e "${YELLOW}※ 재로그인이 필요합니다!${NC}"
    echo "   로그아웃 후 다시 로그인하세요"
fi
