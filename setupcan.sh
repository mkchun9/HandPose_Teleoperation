#!/bin/bash
# PIPER CAN 인터페이스 설정 스크립트

echo "========================================================================"
echo "   🔧 PIPER CAN 인터페이스 설정"
echo "========================================================================"
echo ""

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 1. CAN 인터페이스 확인
echo -e "${YELLOW}[1/5] CAN 인터페이스 확인...${NC}"
if ip link show can0 &> /dev/null; then
    echo -e "${GREEN}✅ can0 인터페이스 존재${NC}"
else
    echo -e "${RED}❌ can0 인터페이스를 찾을 수 없습니다${NC}"
    echo "   CAN 하드웨어가 연결되어 있는지 확인하세요"
    echo "   (USB-to-CAN 어댑터 또는 내장 CAN 포트)"
fi

# 2. CAN 인터페이스 상태 확인
echo -e "\n${YELLOW}[2/5] CAN 인터페이스 상태 확인...${NC}"
CAN_STATE=$(ip -details link show can0 2>/dev/null | grep -o "state [A-Z]*" | awk '{print $2}')

if [ "$CAN_STATE" == "UP" ]; then
    echo -e "${GREEN}✅ can0 상태: UP (활성화됨)${NC}"
    BITRATE=$(ip -details link show can0 2>/dev/null | grep -o "bitrate [0-9]*" | awk '{print $2}')
    echo "   비트레이트: ${BITRATE} bps"
else
    echo -e "${RED}⚠️  can0 상태: ${CAN_STATE:-DOWN} (비활성화됨)${NC}"
    echo "   CAN 인터페이스를 활성화해야 합니다"
fi

# 3. CAN 인터페이스 활성화 시도
echo -e "\n${YELLOW}[3/5] CAN 인터페이스 활성화 시도...${NC}"

if [ "$CAN_STATE" != "UP" ]; then
    echo "   CAN 인터페이스를 활성화하겠습니다 (sudo 필요)"
    echo "   비트레이트: 1000000 (1Mbps - PIPER 기본값)"
    
    # can0 다운
    sudo ip link set can0 down 2>/dev/null
    
    # can0 설정 (비트레이트 1Mbps)
    sudo ip link set can0 type can bitrate 1000000
    
    # can0 업
    sudo ip link set can0 up
    
    # 상태 재확인
    sleep 1
    CAN_STATE=$(ip -details link show can0 2>/dev/null | grep -o "state [A-Z]*" | awk '{print $2}')
    
    if [ "$CAN_STATE" == "UP" ]; then
        echo -e "${GREEN}✅ CAN 인터페이스 활성화 성공!${NC}"
    else
        echo -e "${RED}❌ CAN 인터페이스 활성화 실패${NC}"
        echo "   수동으로 시도하세요:"
        echo "   sudo ip link set can0 type can bitrate 1000000"
        echo "   sudo ip link set can0 up"
    fi
else
    echo -e "${GREEN}✅ CAN 인터페이스 이미 활성화되어 있습니다${NC}"
fi

# 4. CAN 통신 테스트
echo -e "\n${YELLOW}[4/5] CAN 통신 테스트...${NC}"

if command -v candump &> /dev/null; then
    echo "   candump 도구로 CAN 메시지 모니터링 중... (3초)"
    timeout 3 candump can0 2>/dev/null &
    CANDUMP_PID=$!
    
    sleep 3
    
    if ps -p $CANDUMP_PID > /dev/null 2>&1; then
        kill $CANDUMP_PID 2>/dev/null
    fi
    
    echo "   (메시지가 보이면 CAN 통신 정상)"
else
    echo -e "${YELLOW}⚠️  candump 도구 없음 (선택사항)${NC}"
    echo "   설치: sudo apt-get install can-utils"
fi

# 5. 자동 시작 설정 (선택)
echo -e "\n${YELLOW}[5/5] 부팅 시 자동 활성화 설정 (선택)${NC}"
read -p "부팅 시 can0를 자동으로 활성화하시겠습니까? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "   /etc/network/interfaces 수정..."
    
    # 백업
    sudo cp /etc/network/interfaces /etc/network/interfaces.backup 2>/dev/null
    
    # can0 설정 추가
    if ! grep -q "auto can0" /etc/network/interfaces 2>/dev/null; then
        echo "" | sudo tee -a /etc/network/interfaces
        echo "# CAN interface for PIPER" | sudo tee -a /etc/network/interfaces
        echo "auto can0" | sudo tee -a /etc/network/interfaces
        echo "iface can0 inet manual" | sudo tee -a /etc/network/interfaces
        echo "    pre-up ip link set can0 type can bitrate 1000000" | sudo tee -a /etc/network/interfaces
        echo "    up ip link set can0 up" | sudo tee -a /etc/network/interfaces
        echo "    down ip link set can0 down" | sudo tee -a /etc/network/interfaces
        
        echo -e "${GREEN}✅ 자동 시작 설정 완료${NC}"
    else
        echo -e "${GREEN}✅ 이미 설정되어 있습니다${NC}"
    fi
fi

# 요약
echo ""
echo "========================================================================"
echo "   📋 설정 요약"
echo "========================================================================"
echo ""

CAN_STATE=$(ip -details link show can0 2>/dev/null | grep -o "state [A-Z]*" | awk '{print $2}')
BITRATE=$(ip -details link show can0 2>/dev/null | grep -o "bitrate [0-9]*" | awk '{print $2}')

if [ "$CAN_STATE" == "UP" ]; then
    echo -e "${GREEN}✅ CAN 인터페이스: 활성화됨${NC}"
    echo "   포트: can0"
    echo "   비트레이트: ${BITRATE:-1000000} bps"
    echo ""
    echo -e "${GREEN}👉 이제 PIPER 프로그램을 실행할 수 있습니다!${NC}"
    echo "   python3 full_hand_control.py"
else
    echo -e "${RED}❌ CAN 인터페이스: 비활성화됨${NC}"
    echo ""
    echo "수동 설정 방법:"
    echo "   sudo ip link set can0 type can bitrate 1000000"
    echo "   sudo ip link set can0 up"
fi

echo ""
echo "========================================================================"