#!/usr/bin/env python3
"""
PIPER CAN 통신 진단 도구
실제 CAN 버스 상태와 PIPER 로봇 연결을 확인합니다
"""

import subprocess
import time
import sys

print("=" * 70)
print("   🔍 PIPER CAN 통신 진단")
print("=" * 70 + "\n")

# 1. CAN 인터페이스 상태
print("[1/6] CAN 인터페이스 상태 확인...")
try:
    result = subprocess.run(['ip', '-details', 'link', 'show', 'can0'], 
                          capture_output=True, text=True)
    
    if 'state UP' in result.stdout:
        print("✅ can0: UP (활성화)")
        
        if 'can state ERROR-ACTIVE' in result.stdout:
            print("✅ CAN 상태: ERROR-ACTIVE (정상)")
        elif 'can state ERROR-PASSIVE' in result.stdout:
            print("⚠️  CAN 상태: ERROR-PASSIVE (오류 많음)")
            print("   → 케이블 연결 확인 필요")
        elif 'can state BUS-OFF' in result.stdout:
            print("❌ CAN 상태: BUS-OFF (통신 불가)")
            print("   → 하드웨어 문제 또는 잘못된 비트레이트")
        
        # 비트레이트 확인
        if 'bitrate 1000000' in result.stdout:
            print("✅ 비트레이트: 1000000 (1Mbps) - PIPER 표준")
        else:
            import re
            bitrate = re.search(r'bitrate (\d+)', result.stdout)
            if bitrate:
                print(f"⚠️  비트레이트: {bitrate.group(1)} (PIPER는 1000000 필요)")
    else:
        print("❌ can0: DOWN (비활성화)")
        print("   실행: sudo ip link set can0 up")
        
except Exception as e:
    print(f"❌ 오류: {e}")

# 2. CAN 오류 통계
print("\n[2/6] CAN 오류 통계...")
try:
    result = subprocess.run(['ip', '-s', 'link', 'show', 'can0'], 
                          capture_output=True, text=True)
    
    lines = result.stdout.split('\n')
    for i, line in enumerate(lines):
        if 'RX:' in line or 'TX:' in line:
            print(f"   {line.strip()}")
            if i + 1 < len(lines):
                print(f"   {lines[i+1].strip()}")
    
    # 오류 체크
    if 'errors' in result.stdout:
        import re
        errors = re.findall(r'errors (\d+)', result.stdout)
        total_errors = sum(int(e) for e in errors)
        
        if total_errors > 0:
            print(f"\n⚠️  총 오류: {total_errors}")
            print("   오류가 계속 증가하면 하드웨어 문제입니다")
        else:
            print("\n✅ 오류 없음")
            
except Exception as e:
    print(f"❌ 오류: {e}")

# 3. CAN 메시지 모니터링
print("\n[3/6] CAN 메시지 모니터링 (3초)...")
try:
    print("   candump로 PIPER 메시지 감지 시도...")
    
    # candump 실행
    proc = subprocess.Popen(['candump', 'can0', '-n', '10'], 
                           stdout=subprocess.PIPE, 
                           stderr=subprocess.PIPE,
                           text=True)
    
    try:
        stdout, stderr = proc.communicate(timeout=3)
        
        if stdout:
            lines = stdout.strip().split('\n')
            print(f"✅ {len(lines)}개 메시지 수신:")
            for line in lines[:5]:  # 처음 5개만
                print(f"   {line}")
            if len(lines) > 5:
                print(f"   ... (외 {len(lines)-5}개)")
            print("\n   → PIPER가 메시지를 보내고 있습니다 ✅")
        else:
            print("❌ 메시지 없음 (3초 동안)")
            print("   → PIPER가 응답하지 않습니다")
            print("   체크:")
            print("     1. PIPER 전원 ON?")
            print("     2. CAN 케이블 연결?")
            print("     3. 케이블 극성 올바름?")
            
    except subprocess.TimeoutExpired:
        proc.kill()
        print("⚠️  타임아웃 (메시지 없음)")
        
except FileNotFoundError:
    print("⚠️  candump를 찾을 수 없습니다")
    print("   설치: sudo apt-get install can-utils")
except Exception as e:
    print(f"❌ 오류: {e}")

# 4. PIPER SDK 연결 테스트
print("\n[4/6] PIPER SDK 연결 테스트...")
try:
    from piper_sdk import C_PiperInterface
    
    print("   PIPER 객체 생성 중...")
    piper = C_PiperInterface()

    print("   포트 연결 시도...")
    # ConnectPort() does not return a numeric status in the SDK; it sets internal connection state.
    try:
        piper.ConnectPort()
    except Exception as e:
        print(f"❌ SDK 연결 시도 중 예외 발생: {e}")
        raise

    # Use SDK API to query connection status
    connected = False
    try:
        # get_connect_status() returns True when connected
        if hasattr(piper, 'get_connect_status'):
            connected = piper.get_connect_status()
        elif hasattr(piper, 'GetConnectStatus'):
            connected = piper.GetConnectStatus()
    except Exception:
        connected = False

    if connected:
        print("✅ SDK 연결 성공")

        # 간단한 명령 테스트
        print("   암 활성화 테스트...")
        try:
            piper.EnableArm(7)
            print("✅ 명령 전송 성공")
        except Exception as e:
            print(f"❌ 명령 전송 실패: {e}")

        # 연결 해제
        try:
            # prefer DisconnectPort name in SDK
            if hasattr(piper, 'DisconnectPort'):
                piper.DisconnectPort()
            elif hasattr(piper, 'DisConnectPort'):
                piper.DisConnectPort()
        except Exception as e:
            print(f"⚠️  연결 해제 중 오류: {e}")
    else:
        print("❌ SDK 연결 실패 (포트는 열렸지만 SDK에서 연결 상태를 확인하지 못했습니다)")
        
except Exception as e:
    print(f"❌ SDK 오류: {e}")

# 5. 하드웨어 체크리스트
print("\n[5/6] 하드웨어 체크리스트...")
print("   [ ] PIPER 전원 스위치 ON")
print("   [ ] 전원 LED 점등")
print("   [ ] CAN 케이블 단단히 연결")
print("   [ ] CAN_H, CAN_L 올바른 극성")
print("   [ ] USB-to-CAN 어댑터 연결 (사용 시)")
print("   [ ] 비상정지 버튼 해제")
print("   [ ] 30초 부팅 대기")

# 6. 권장 조치
print("\n[6/6] 권장 조치...")

# CAN 메시지가 없다면
print("\n만약 CAN 메시지가 수신되지 않는다면:")
print("   1. PIPER 전원 재시작")
print("      - 전원 OFF → 10초 대기 → 전원 ON")
print("      - 30초 부팅 대기")
print("")
print("   2. CAN 케이블 재연결")
print("      - 케이블 뽑기 → 확인 → 다시 꽂기")
print("      - CAN_H와 CAN_L 극성 확인")
print("")
print("   3. CAN 인터페이스 재시작")
print("      sudo ip link set can0 down")
print("      sudo ip link set can0 type can bitrate 1000000")
print("      sudo ip link set can0 up")
print("")
print("   4. 다른 CAN 도구로 테스트")
print("      candump can0  # 실시간 모니터링")
print("      cansend can0 123#DEADBEEF  # 테스트 전송")

print("\n" + "=" * 70)
print("   진단 완료")
print("=" * 70)

# 최종 상태
print("\n✅ 다음 단계:")
print("   - CAN 메시지 수신 확인됨 → python3 demo_v3.py 실행")
print("   - CAN 메시지 없음 → 위 체크리스트 확인")
print("\n" + "=" * 70)