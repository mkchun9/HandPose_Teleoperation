# 🚀 PIPER ROS Noetic 빠른 시작

## ⚡ 한 줄 설치 (Ubuntu 20.04)

```bash
# 실행 권한 부여 및 설치
chmod +x install_ros_noetic.sh
./install_ros_noetic.sh
```

## 📦 포함된 파일

| 파일 | 설명 |
|------|------|
| `demo_v3_safe.py` | 안전 제어 (RViz 없음) |
| `demo_v3_rviz.py` | RViz 시각화 포함 |
| `piper_simple.launch` | 간단한 RViz 실행 |
| `piper.rviz` | RViz 설정 |
| `install_ros_noetic.sh` | 자동 설치 스크립트 |

## 🎯 빠른 실행 (3가지 방법)

### 방법 1: RViz 없이 실행 (가장 간단)
```bash
python3 demo_v3_safe.py
```

### 방법 2: RViz 포함 (추천)
```bash
# 터미널 1
roscore

# 터미널 2  
roslaunch piper_simple.launch

# 터미널 3
python3 demo_v3_rviz.py
```

### 방법 3: 한 줄 실행 (roscore 실행 중일 때)
```bash
python3 demo_v3_rviz.py & sleep 2 && roslaunch piper_simple.launch
```

## 🎮 조작법

| 키 | 동작 |
|---|---|
| **C** | 캘리브레이션 (홈 설정) |
| **SPACE** | 제어 시작/일시정지 |
| **H** | 홈 포지션 (동작 중단 + 복귀) |
| **Q** | 안전 종료 |
| **Ctrl+C** | 비상 종료 (안전) |

## 🎥 손 동작 → 로봇 동작 (좌측 카메라)

| 손 동작 | 로봇 결과 |
|---------|-----------|
| 👈 왼쪽 | ⬆️ 앞으로 |
| 👉 오른쪽 | ⬇️ 뒤로 |
| ☝️ 위 | ⬆️ 위로 |
| 👇 아래 | ⬇️ 아래로 (Z 하한선까지) |
| 🤚→📷 가까이 | ⬅️ 왼쪽 + 🔄 왼쪽 회전 |
| 📷←🤚 멀리 | ➡️ 오른쪽 + 🔄 오른쪽 회전 |
| ✊ 손가락 오므리기 | 그리퍼 닫기 |
| ✋ 손가락 펴기 | 그리퍼 열기 |

## 🛡️ 안전 기능

- ✅ 모든 종료 방법에서 홈 복귀 보장
- ✅ Ctrl+C로도 안전 종료
- ✅ Z축 하한선 보호 (홈 아래로 안 내려감)
- ✅ H 키로 언제든 현재 동작 중단 + 홈 복귀
- ✅ 작업 공간 자동 제한

## 📊 RViz 시각화 (활성화 시)

- ✅ 실시간 관절 각도 (~20Hz)
- ✅ End effector 위치
- ✅ TF transforms
- ✅ 그리퍼 상태

## 🔍 문제 해결

### "Unable to contact ROS master"
```bash
# 해결: ROS Master 실행
roscore &
```

### "No module named 'rospy'"
```bash
# 해결: ROS 환경 설정
source /opt/ros/noetic/setup.bash

# 또는 설치 스크립트 재실행
./install_ros_noetic.sh
```

### RViz에 아무것도 안 보임
```bash
# 1. Fixed Frame 확인 (RViz)
# Displays → Global Options → Fixed Frame = "world"

# 2. TF 활성화 (RViz)
# Displays → TF → Enabled ✓

# 3. Axes 추가 (RViz)
# Add → Axes

# 4. Topic 확인 (터미널)
rostopic hz /joint_states
```

### Python 2 vs 3 오류
```bash
# 항상 python3 사용!
python3 demo_v3_rviz.py  # ✅ 올바름
python demo_v3_rviz.py   # ❌ 틀림 (Python 2)
```

## 📚 상세 문서

- **[NOETIC_SETUP.md](NOETIC_SETUP.md)** - 완전한 설치 가이드
- **[SAFETY_V3_GUIDE.md](SAFETY_V3_GUIDE.md)** - 안전 기능 상세
- **[RVIZ_GUIDE.md](RVIZ_GUIDE.md)** - RViz 사용법
- **[COORDINATE_MAPPING.md](COORDINATE_MAPPING.md)** - 좌표 변환

## ✅ 설치 확인

```bash
# ROS Noetic 확인
rosversion -d
# 출력: noetic

# Python 3 확인
python3 --version
# 출력: Python 3.8.x

# RViz 확인
which rviz
# 출력: /opt/ros/noetic/bin/rviz

# 모두 OK면 준비 완료! ✅
```

## 🎬 첫 실행 예시

```bash
# 1. ROS 시작
user@ubuntu:~$ roscore &
[1] 12345
... roscore started ...

# 2. 프로그램 실행
user@ubuntu:~$ python3 demo_v3_rviz.py
============================================================
   🛡️  PIPER 안전 제어 + RViz v3
   ✋ 좌측 카메라 최적화 + 실시간 시각화
   📷 Intel RealSense D435I
============================================================

✅ ROS Noetic 모듈 로드 성공
✅ ROS Noetic 초기화 완료
PIPER 로봇 연결 중...
✅ PIPER CAN 연결 성공
...

# 3. 다른 터미널에서 RViz
user@ubuntu:~$ roslaunch piper_simple.launch
... RViz starting ...

# 4. 손 제어 시작!
# [C] 캘리브레이션
# [SPACE] 제어 시작
# 🎉 성공!
```

## 💡 팁

- 처음에는 **천천히** 움직이세요
- **캘리브레이션**은 편안한 위치에서
- **H 키**는 비상 정지 + 홈 복귀
- RViz에서 로봇 움직임을 실시간 확인
- Z축 하한선 때문에 일정 높이 아래로 안 내려감 (안전)

## 🆘 도움말

문제가 있으면:
1. `NOETIC_SETUP.md` 확인
2. `rostopic list`로 topic 확인
3. `rostopic hz /joint_states` 로 데이터 확인
4. 프로그램 재시작

---

**🚀 즐거운 로봇 제어 되세요!**

**ROS Noetic + Ubuntu 20.04 + Python 3**

**버전:** v3.0  
**작성일:** 2025-11-06
