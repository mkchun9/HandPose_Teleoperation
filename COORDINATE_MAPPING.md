# 📐 카메라 좌표계 매핑 가이드

## 🎥 카메라 설치 위치: 손의 좌측

### 좌표계 변환 개요

```
카메라 시점 (왼쪽에서 봄)
┌─────────────────┐
│                 │
│   손 →  📷      │
│                 │
└─────────────────┘

로봇 시점 (위에서 봄)
       ↑ X (전후)
       │
       │
  Y ←──┼──  로봇
       │
       │
       ↓
```

## 🔄 좌표 변환 매핑

### 카메라 좌표 → 로봇 좌표

| 카메라 축 | 손 동작 | 로봇 축 | 로봇 동작 | 추가 효과 |
|-----------|---------|---------|-----------|-----------|
| **X축** (좌우) | 손을 좌/우로 | **Z축** (상하) | 위/아래로 이동 | - |
| **Y축** (상하) | 손을 위/아래로 | **X축** (전후) | 앞/뒤로 이동 | - |
| **Z축** (전후) | 손을 가까이/멀리 | **Y축** (좌우) | 좌/우로 이동 | **+ Yaw 회전** |

### 특별 기능: 전후 이동 → 회전

```python
# Z축 이동을 Yaw 회전으로도 매핑
yaw_from_depth = hand_delta[2] * 2.0  # 감도 2배

# 결과:
# 손을 멀리(Z+) → 로봇 오른쪽 회전(Yaw+) + 우측 이동(Y+)
# 손을 가까이(Z-) → 로봇 왼쪽 회전(Yaw-) + 좌측 이동(Y-)
```

## 🎮 실제 동작 예시

### 1. 손을 앞으로(카메라 쪽으로) 🤚→📷
```
카메라: Z축 - (가까워짐)
로봇:   Y축 - (왼쪽 이동)
        Yaw - (왼쪽 회전) 🔄
```
**결과:** 로봇이 왼쪽으로 이동하면서 왼쪽으로 회전

### 2. 손을 뒤로(카메라 반대로) 📷←🤚
```
카메라: Z축 + (멀어짐)
로봇:   Y축 + (오른쪽 이동)
        Yaw + (오른쪽 회전) 🔄
```
**결과:** 로봇이 오른쪽으로 이동하면서 오른쪽으로 회전

### 3. 손을 위로 ☝️
```
카메라: Y축 + (상승)
로봇:   X축 + (전진)
```
**결과:** 로봇이 앞으로 이동

### 4. 손을 아래로 👇
```
카메라: Y축 - (하강)
로봇:   X축 - (후진)
```
**결과:** 로봇이 뒤로 이동

### 5. 손을 오른쪽으로 👉
```
카메라: X축 + (오른쪽)
로봇:   Z축 + (상승)
```
**결과:** 로봇이 위로 올라감

### 6. 손을 왼쪽으로 👈
```
카메라: X축 - (왼쪽)
로봇:   Z축 - (하강)
```
**결과:** 로봇이 아래로 내려감

## 📊 좌표 변환 코드

### 위치 변환
```python
robot_delta = np.array([
    hand_delta[1],   # 카메라 Y (상하) → 로봇 X (전후)
    hand_delta[2],   # 카메라 Z (전후) → 로봇 Y (좌우)
    hand_delta[0]    # 카메라 X (좌우) → 로봇 Z (상하)
])
```

### 회전 매핑
```python
# 전후 이동을 Yaw 회전으로 변환
yaw_from_depth = hand_delta[2] * 2.0  # 감도 2배

# 최종 자세
target_orient[0] += orient_delta[0] * self.orient_scale  # Roll
target_orient[1] += orient_delta[1] * self.orient_scale  # Pitch
target_orient[2] += yaw_from_depth                        # Yaw (전후→회전)
```

## 🎯 감도 조절

### 회전 감도
```python
# 기본값 (감도 2배)
yaw_from_depth = hand_delta[2] * 2.0

# 더 민감하게 (감도 3배)
yaw_from_depth = hand_delta[2] * 3.0

# 덜 민감하게 (감도 1배)
yaw_from_depth = hand_delta[2] * 1.0

# 회전 비활성화
yaw_from_depth = 0
```

### 위치 감도
```python
# demo_v2.py에서 수정
self.pos_scale = 1.0      # 기본값

# 더 민감하게
self.pos_scale = 1.5

# 덜 민감하게
self.pos_scale = 0.7
```

## 🔧 다른 카메라 위치에 맞게 조정

### 정면 촬영 (기본)
```python
robot_delta = np.array([
    hand_delta[2],   # Z → X (전후)
    hand_delta[0],   # X → Y (좌우)
    hand_delta[1]    # Y → Z (상하)
])
yaw_from_depth = 0  # 회전 없음
```

### 우측 촬영
```python
robot_delta = np.array([
    hand_delta[1],    # Y → X (전후)
    -hand_delta[2],   # -Z → Y (좌우, 반전)
    hand_delta[0]     # X → Z (상하)
])
yaw_from_depth = -hand_delta[2] * 2.0  # 반대 방향
```

### 후면 촬영
```python
robot_delta = np.array([
    -hand_delta[2],   # -Z → X (전후, 반전)
    -hand_delta[0],   # -X → Y (좌우, 반전)
    hand_delta[1]     # Y → Z (상하)
])
yaw_from_depth = 0  # 회전 없음
```

## 🎨 시각화

### 좌측 카메라 뷰
```
        👆 Y (위)
        │
        │
        │
📷──────┼──────→ Z (가까이/멀리)
        │      🔄 Yaw 회전도 제어
        │
        ↓ (아래)
    
    X축은 화면 안쪽/바깥쪽 (좌우)
```

### 로봇 뷰 (위에서 봄)
```
        ↑ X (앞)
        │
        │
        │
    ←───┼───→ Y (좌우)
        │
        │
        ↓ (뒤)
    
    Z축은 위/아래
    Yaw: Y축을 따라 회전 (시계/반시계)
```

## 💡 사용 팁

### 1. 자연스러운 제어
```
✅ 손을 카메라 쪽으로 → 로봇 왼쪽 회전
✅ 손을 카메라 반대로 → 로봇 오른쪽 회전
✅ 손을 위로 → 로봇 전진
✅ 손을 아래로 → 로봇 후진
```

### 2. 회전 활용
```
물체를 집을 때:
1. 손을 멀리 → 로봇 오른쪽 회전 (각도 맞추기)
2. 손을 가까이 → 로봇 왼쪽 회전 (각도 조정)
3. 손가락 오므리기 → 그리퍼 닫기
```

### 3. 정밀 제어
```
# 회전 감도를 낮춰서 더 정밀하게
yaw_from_depth = hand_delta[2] * 1.0  # 감도 낮춤

# 위치만 제어하고 회전 끄기
yaw_from_depth = 0
```

## 🔍 문제 해결

### Q: 로봇이 반대로 움직여요
**A:** 카메라 위치를 다시 확인하고 좌표 반전
```python
robot_delta = np.array([
    -hand_delta[1],   # 부호 반전
    -hand_delta[2],   # 부호 반전
    hand_delta[0]
])
```

### Q: 회전이 너무 민감해요
**A:** 회전 감도 낮추기
```python
yaw_from_depth = hand_delta[2] * 1.0  # 2.0 → 1.0
```

### Q: 회전이 반대 방향이에요
**A:** 부호 반전
```python
yaw_from_depth = -hand_delta[2] * 2.0  # 음수로 변경
```

### Q: 위아래가 반대로 움직여요
**A:** Z축 매핑 반전
```python
robot_delta = np.array([
    hand_delta[1],
    hand_delta[2],
    -hand_delta[0]    # 부호 반전
])
```

## 📐 캘리브레이션 팁

### 1. 중립 자세 확인
```
캘리브레이션 시:
✅ 손을 편안한 위치에
✅ 손바닥이 카메라를 향하도록
✅ 팔을 자연스럽게
```

### 2. 테스트 순서
```
1. 캘리브레이션 (C 키)
2. 제어 활성화 (SPACE)
3. 천천히 각 방향으로 테스트:
   - 위/아래
   - 좌/우
   - 가까이/멀리 (회전 확인)
```

### 3. 미세 조정
```python
# 각 축의 감도를 개별 조정
robot_delta = np.array([
    hand_delta[1] * 1.0,   # Y축 감도
    hand_delta[2] * 0.8,   # Z축 감도 (회전과 함께)
    hand_delta[0] * 1.2    # X축 감도
])
```

## 🎓 고급 설정

### 비선형 매핑
```python
# 중앙에서는 둔감하게, 끝으로 갈수록 민감하게
def nonlinear_mapping(delta, threshold=0.05):
    sign = np.sign(delta)
    abs_delta = abs(delta)
    if abs_delta < threshold:
        return delta * 0.5  # 중앙 영역 둔감
    else:
        return sign * (threshold * 0.5 + (abs_delta - threshold) * 1.5)

robot_delta = np.array([
    nonlinear_mapping(hand_delta[1]),
    nonlinear_mapping(hand_delta[2]),
    nonlinear_mapping(hand_delta[0])
])
```

### 데드존 설정
```python
# 작은 움직임 무시
DEADZONE = 0.01  # 1cm

hand_delta_filtered = hand_delta.copy()
hand_delta_filtered[abs(hand_delta) < DEADZONE] = 0

robot_delta = np.array([
    hand_delta_filtered[1],
    hand_delta_filtered[2],
    hand_delta_filtered[0]
])
```

## 📝 요약

### 핵심 포인트
1. **좌측 카메라**: 특별한 좌표 변환 필요
2. **전후 이동 → 회전**: 자연스러운 제어
3. **감도 조절**: 사용자 선호에 맞게
4. **테스트 필수**: 캘리브레이션 후 확인

### 빠른 참조
```python
# 위치 매핑
X(전후) ← Y(상하)
Y(좌우) ← Z(전후)
Z(상하) ← X(좌우)

# 회전 추가
Yaw ← Z * 2.0
```

---

**버전:** v2.1  
**작성일:** 2025-11-06  
**작성자:** Claude

좌측 카메라로 자연스러운 제어를 즐기세요! 🎥🤖
