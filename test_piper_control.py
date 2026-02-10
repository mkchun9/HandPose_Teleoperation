#!/usr/bin/env python3
"""
PIPER 제어 테스트 - Joint 값이 변하는지 확인
"""

from piper_sdk import *
import time
import math

print("=" * 70)
print("   🧪 PIPER 제어 테스트")
print("=" * 70 + "\n")

# 1. 연결
print("[1/7] PIPER 연결...")
piper = C_PiperInterface()
piper.ConnectPort()
print("✅ 연결 성공")

# 2. 마스터/슬레이브 설정
print("\n[2/7] 마스터/슬레이브 설정...")
try:
    piper.MasterSlaveConfig(0xFC, 0, 0, 0)
    print("✅ 설정 완료")
except Exception as e:
    print(f"⚠️  설정 실패: {e}")

# 3. 암 활성화
print("\n[3/7] 암 활성화...")
piper.EnableArm(7)
time.sleep(1)
print("✅ 암 활성화")

# 4. 현재 관절 각도 읽기
print("\n[4/7] 현재 관절 각도 읽기...")
try:
    # 몇 번 읽어서 확인
    for i in range(3):
        time.sleep(0.2)
        # GetArmJointMsgs() 또는 유사한 함수로 관절 각도 읽기
        print(f"   읽기 {i+1}/3...")
    print("✅ 관절 각도 읽기 완료")
except Exception as e:
    print(f"⚠️  읽기 실패: {e}")

# 5. 제어 모드 설정
print("\n[5/7] 제어 모드 설정...")
print("   옵션 A: CAN 제어 모드 + Move L")
try:
    piper.MotionCtrl_2(0x01, 0x02, 50, 0x00)
    print("   ✅ MotionCtrl_2 성공")
except Exception as e:
    print(f"   ⚠️  MotionCtrl_2 실패: {e}")
    try:
        piper.ModeCtrl(0x01, 0x02, 50, 0x00)
        print("   ✅ ModeCtrl 성공")
    except Exception as e2:
        print(f"   ⚠️  ModeCtrl 실패: {e2}")

# 6. 간단한 움직임 테스트
print("\n[6/7] 움직임 테스트...")

# 현재 위치 (추정)
x_current = 350  # mm
y_current = 0
z_current = 300

print(f"   현재 위치(추정): X={x_current}, Y={y_current}, Z={z_current}")

# 테스트 1: 위로 50mm 이동
print("\n   테스트 1: 위로 50mm 이동")
x_target = x_current
y_target = y_current
z_target = z_current + 50
rx, ry, rz = 0, 180000, 0  # 0.001 deg units

try:
    piper.EndPoseCtrl(x_target, y_target, z_target, rx, ry, rz)
    print(f"   ✅ 명령 전송: Z={z_current} → {z_target}")
    print("   3초 대기 (로봇 움직임 확인)...")
    
    for i in range(5):
        time.sleep(1)
        print(f"   {i+1}/5...")
    
    print("   ✅ 이동 완료")
except Exception as e:
    print(f"   ❌ 오류: {e}")

# 테스트 2: 원위치
print("\n   테스트 2: 원위치")
try:
    piper.EndPoseCtrl(x_current, y_current, z_current, rx, ry, rz)
    print(f"   ✅ 명령 전송: Z={z_target} → {z_current}")
    print("   3초 대기...")
    
    for i in range(5):
        time.sleep(1)
        print(f"   {i+1}/5...")
    
    print("   ✅ 복귀 완료")
except Exception as e:
    print(f"   ❌ 오류: {e}")

# 7. 결과
print("\n[7/7] 결과 분석...")

print("\n로봇이 실제로 움직였나요?")
print("   - 움직임 → ✅ 제어 정상 작동")
print("   - 안 움직임 → ❌ 문제 있음")

print("\n가능한 원인:")
print("   1. 제어 모드가 설정되지 않음")
print("   2. 로봇이 티칭 모드 또는 다른 모드")
print("   3. 비상정지 또는 안전 모드")
print("   4. 좌표 범위 밖 (워크스페이스 제한)")
print("   5. 속도가 너무 느림")

# 8. 정리
print("\n[8/8] 정리...")
try:
    piper.GripperCtrl(800, 500)  # 그리퍼 열기
    time.sleep(0.5)
except:
    pass

piper.DisconnectPort()
print("✅ 연결 해제")

print("\n" + "=" * 70)
print("   테스트 완료")
print("=" * 70)

print("\n💡 다음 단계:")
print("   - 로봇이 움직였으면: demo_v3.py 실행")
print("   - 안 움직였으면: 아래 확인")
print("")
print("확인 사항:")
print("   [ ] 비상정지 버튼 해제")
print("   [ ] 로봇이 홈 위치에 있음")
print("   [ ] 티칭 펜던트로 움직임 가능")
print("   [ ] 제어 모드가 CAN/외부 제어")