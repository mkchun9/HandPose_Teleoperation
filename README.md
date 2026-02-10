# 🤖 PIPER 손동작 인식 텔레오퍼레이션 시스템

Agilex PIPER 로봇 암을 위한 손동작 인식 기반 실시간 텔레오퍼레이션 체험 프로그램

## 🎯 프로젝트 개요

이 시스템은 웹캠으로 손동작을 인식하여 PIPER 6자유도 로봇 암을 직관적으로 제어할 수 있는 체험 프로그램입니다.

### 주요 기능
- ✋ **실시간 손 추적**: MediaPipe를 사용한 고정밀 손 랜드마크 검출
- 🎮 **직관적인 제어**: 손 위치 → 로봇 엔드이펙터 위치 매핑
- 🤏 **제스처 인식**: 핀치 제스처로 그리퍼 제어
- 📊 **실시간 피드백**: 시각적 인터페이스로 로봇 상태 모니터링
- 🎚️ **안전 제한**: 작업 공간 경계 설정으로 안전 보장

## 📦 시스템 요구사항

### 하드웨어
- Agilex PIPER 로봇 암
- 웹캠 또는 USB 카메라
- Ubuntu 18.04/20.04 (ROS Noetic) 또는 Ubuntu 22.04 (ROS2 Humble)

### 소프트웨어
- Python 3.8+
- ROS Noetic
- OpenCV 4.8+
- MediaPipe 0.10+
- NumPy 1.24+

## 🚀 설치 방법

### 1. 저장소 클론
```bash
cd ~/catkin_ws/src  # ROS1의 경우
# 또는
cd ~/ros2_ws/src    # ROS2의 경우

git clone https://github.com/mkchun9/HandPose_Teleoperation.git
cd HandPose_Teleoperation
```

### 2. Python 패키지 설치
```bash
pip3 install -r requirements.txt
```

### 3. PIPER SDK 설치
```bash
# PIPER SDK는 AgileX Robotics 공식 저장소에서 다운로드
git clone https://github.com/agilexrobotics/piper_sdk.git
cd piper_sdk
pip3 install -e .
```

### 4. ROS 패키지 빌드
```bash
cd ~/catkin_ws  # 또는 ~/ros2_ws
catkin_make     # 또는 colcon build
source devel/setup.bash  # 또는 install/setup.bash
```

## 🎮 사용 방법

### 방법 1: 단독 실행 (Python만 사용)
```bash
python3 piper_hand_teleoperation.py
```

### 방법 2: ROS 런치 파일 사용 (권장)
```bash
# 터미널 1: PIPER 컨트롤러 실행
rosrun piper_teleoperation piper_controller.py

# 터미널 2: 손동작 텔레오퍼레이션 실행
rosrun piper_teleoperation piper_hand_teleoperation.py
```

### 방법 3: 올인원 런치
```bash
roslaunch piper_teleoperation piper_teleoperation.launch
```

## 🎯 조작 방법

### 초기 설정
1. **카메라 앞에 손 위치**: 손바닥이 카메라를 향하도록 위치
2. **캘리브레이션**: `C` 키를 눌러 현재 손 위치를 로봇 홈 위치로 설정
3. **제어 시작**: 손을 움직이면 로봇이 따라 움직입니다

### 키보드 단축키
| 키 | 기능 |
|---|---|
| `C` | 캘리브레이션 (현재 손 위치를 기준점으로 설정) |
| `G` | 그리퍼 열기/닫기 토글 |
| `Q` | 프로그램 종료 |

### 손동작 매핑
```
손 움직임         →  로봇 움직임
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
좌/우 (X축)      →  좌/우 (Y축)
앞/뒤 (Y축)      →  앞/뒤 (X축)
위/아래 (Z축)    →  위/아래 (Z축)
핀치 제스처      →  그리퍼 제어
```

## ⚙️ 설정 및 커스터마이징

### 작업 공간 조정
`piper_hand_teleoperation.py` 파일에서 작업 공간 범위를 수정:

```python
self.workspace = {
    'x_min': 0.2, 'x_max': 0.5,  # 미터 단위
    'y_min': -0.3, 'y_max': 0.3,
    'z_min': 0.1, 'z_max': 0.5
}
```

### 제어 감도 조정
```python
self.scale_factor = 0.8      # 손 움직임 스케일 (0.5 ~ 1.5 권장)
self.smoothing_factor = 0.3  # 스무딩 정도 (0.1 ~ 0.5 권장)
```

### 카메라 설정
```python
self.cap = cv2.VideoCapture(0)  # 0: 기본 카메라, 1: 외부 카메라
self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
```

## 📊 시스템 아키텍처

```
┌─────────────────┐
│   웹캠 입력      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  MediaPipe      │
│  손 랜드마크     │
│  검출 (21점)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  좌표 변환 및    │
│  매핑 알고리즘   │
│  - 캘리브레이션  │
│  - 스케일링      │
│  - 스무딩        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  ROS 메시지     │
│  PoseStamped    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  PIPER SDK      │
│  로봇 제어       │
└─────────────────┘
```

## 🔧 문제 해결

### 카메라가 인식되지 않음
```bash
# 카메라 장치 확인
ls /dev/video*

# 카메라 권한 부여
sudo chmod 666 /dev/video0
```

### PIPER 로봇 연결 실패
```bash
# USB 포트 권한 확인
sudo chmod 666 /dev/ttyUSB0

# PIPER SDK 설치 확인
python3 -c "import piper_sdk; print('SDK OK')"
```

### 손 검출이 불안정함
- 조명을 밝게 설정
- 카메라와 손 사이 거리를 50-80cm 유지
- 배경을 단순하게 설정
- `min_detection_confidence` 값을 낮춤 (0.5로 변경)

### 로봇 움직임이 부자연스러움
- `smoothing_factor`를 높여 스무딩 증가 (0.5로 변경)
- `scale_factor`를 낮춰 민감도 감소 (0.5로 변경)

## 🎓 체험 프로그램 운영 가이드

### 체험자 안내 사항
1. **안전 교육**
   - 로봇 작업 공간 내 신체 부위 접근 금지
   - 비상정지 버튼 위치 확인
   - 이상 동작 시 즉시 `Q` 키로 종료

2. **체험 시나리오 예시**
   - **레벨 1**: 지정된 위치로 이동하기
   - **레벨 2**: 물체 집어 올리기
   - **레벨 3**: 물체를 다른 위치로 옮기기
   - **레벨 4**: 정밀 조작 (컵에 물건 넣기 등)

3. **체험 시간**: 1인당 5-10분 권장

## 📈 To-DO

- [ ] 손 회전 인식으로 엔드이펙터 자세 제어
- [ ] 양손 모드 (한 손: 위치, 다른 손: 자세)
- [ ] 제스처 커맨드 추가 (손가락 개수로 모드 전환)
- [ ] VR 헤드셋 연동
- [ ] 햅틱 피드백 지원
- [ ] 다중 로봇 동시 제어
- [ ] 웹 기반 인터페이스

## 📝 License

MIT License

## 👥 Reference

- AgileX Robotics - PIPER 로봇 암
- Google MediaPipe - 손 추적 라이브러리

## 🙏 감사의 말

이 프로젝트는 AgileX Robotics의 PIPER 로봇과 Google의 MediaPipe 라이브러리를 기반으로 개발되었습니다.

---

**⚠️ 주의사항**: 이 시스템은 교육 및 체험 목적으로 설계되었습니다. 산업 현장에서 사용 시 추가적인 안전 장치와 검증이 필요합니다.
