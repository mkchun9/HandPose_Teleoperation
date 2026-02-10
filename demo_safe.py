#!/usr/bin/env python3
"""
PIPER 로봇 팔 안전 제어 시스템 v3
- 안전한 종료 (Ctrl+C, Q 모두 홈→리셋 보장)
- 좌측 카메라 뷰 최적화
- Z축 하한선 보호
- 손가락 간격 그리퍼 제어
Intel RealSense D435I + MediaPipe

안전 기능:
1. 모든 종료 시 홈 포지션 복귀 보장
2. Signal handler로 Ctrl+C 안전 처리
3. Z축 하한선 보호 (홈 포지션 아래로 안 내려감)
4. 좌측 카메라 좌표계 정확한 매핑
"""

import cv2
import numpy as np
import pyrealsense2 as rs
import mediapipe as mp
import time
import sys
import math
import signal
import atexit
from collections import deque

# PIPER SDK
from piper_sdk import *


class SafePiperTeleoperation:
    """안전한 PIPER 텔레오퍼레이션 시스템"""
    
    def __init__(self):
        """초기화"""
        print("\n" + "=" * 70)
        print("   🛡️  PIPER 안전 제어 시스템 v3")
        print("   ✋ 좌측 카메라 최적화 + Z축 하한선 보호")
        print("   📷 Intel RealSense D435I")
        print("=" * 70 + "\n")
        
        # 안전 종료를 위한 플래그
        self.shutdown_in_progress = False
        self.emergency_shutdown = False
        
        # PIPER 로봇 초기화
        self.piper = None
        self.initialize_robot()
        
        # RealSense 초기화
        self.initialize_camera()
        
        # MediaPipe 초기화
        self.initialize_mediapipe()
        
        # 작업 공간 (미터)
        self.workspace = {
            'x_min': -0.3, 'x_max': 0.5,
            'y_min': -0.3, 'y_max': 0.5,
            'z_min': 0.15, 'z_max': 0.5
        }
        
        # 홈 포지션 Z축 저장 (안전 하한선)
        self.home_z_limit = 0.25  # 250mm (기본 안전 높이)
        
        # 캘리브레이션
        self.is_calibrated = False
        self.hand_home_pos = None
        self.hand_home_orient = None
        self.robot_home_pos = np.array([0.35, 0.0, 0.3])      # 미터
        self.robot_home_orient = np.array([0.0, math.pi, 0.0])  # 라디안
        
        # 제어 파라미터
        self.pos_scale = 1.0
        self.orient_scale = 0.5
        self.pos_smooth = 0.3
        self.orient_smooth = 0.4
        
        # NumPy 배열로 초기화
        self.prev_position = np.array(self.robot_home_pos)
        self.prev_orientation = np.array(self.robot_home_orient)
        
        # 상태
        self.is_running = True
        self.gripper_open = True
        self.control_enabled = False
        
        # 성능
        self.last_command_time = 0
        self.command_interval = 0.05  # 20Hz
        
        # Signal handler 등록 (Ctrl+C 안전 처리)
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        # atexit 등록 (프로그램 종료 시 자동 실행)
        atexit.register(self.emergency_cleanup)
        
        print("\n✅ 시스템 준비 완료!")
        print("📌 [C] 캘리브레이션  [SPACE] 제어 On/Off  [H] 홈  [Q] 종료\n")
    
    def signal_handler(self, signum, frame):
        """Signal handler (Ctrl+C 등)"""
        print("\n\n⚠️  중단 신호 감지! 안전 종료 시작...")
        self.emergency_shutdown = True
        self.is_running = False
    
    def emergency_cleanup(self):
        """비상 정리 (atexit에서 자동 호출)"""
        if self.shutdown_in_progress:
            return  # 이미 종료 중이면 중복 실행 방지
        
        if self.emergency_shutdown and self.piper:
            print("\n🚨 비상 종료 모드 활성화")
            self.safe_shutdown()
    
    def initialize_robot(self):
        """로봇 초기화"""
        print("PIPER 로봇 연결 중...")
        try:
            # 1단계: 인터페이스 생성
            self.piper = C_PiperInterface("can0")
            time.sleep(0.2)
            
            # 2단계: 포트 연결
            self.piper.ConnectPort()
            time.sleep(0.5)
            print("✅ PIPER CAN 연결 성공")
            
            # 3단계: 로봇 활성화
            print("🔧 로봇 팔 활성화 중...")
            self.piper.EnableArm(7)
            time.sleep(1.0)
            
            # 활성화 확인
            enable_status = self.piper.GetArmEnableStatus()
            if all(enable_status):
                print("✅ 로봇 팔 활성화 완료")
            else:
                print(f"⚠️  일부 관절 미활성화: {enable_status}")
            
            # 4단계: 제어 모드 설정
            print("🔧 제어 모드 설정 중...")
            self.piper.ModeCtrl(
                ctrl_mode=0x01,
                move_mode=0x00,      # MOVE P (Cartesian)
                move_spd_rate_ctrl=20,
                is_mit_mode=0x00
            )
            time.sleep(0.3)
            print("✅ 제어 모드 설정 완료")
            
            # 5단계: 그리퍼 초기화
            print("🔧 그리퍼 초기화 중...")
            self.piper.GripperCtrl(
                gripper_angle=50000,
                gripper_effort=1000,
                gripper_code=0x03,
                set_zero=0x00
            )
            time.sleep(0.5)
            print("✅ 그리퍼 초기화 완료")
            
            # 6단계: 홈 포지션으로 이동
            print("🏠 홈 포지션으로 이동 중...")
            self.move_to_home_position()
            
            # 홈 포지션의 Z축 저장 (안전 하한선)
            try:
                end_pose = self.piper.GetArmEndPoseMsgs()
                self.home_z_limit = end_pose.end_pose.Z_axis / 1000000  # μm → m
                print(f"🛡️  Z축 안전 하한선: {self.home_z_limit:.3f}m")
            except:
                self.home_z_limit = 0.25  # 기본값
            
            print("✅ 초기화 완료!")
            
        except Exception as e:
            print(f"❌ PIPER 초기화 실패: {e}")
            import traceback
            traceback.print_exc()
            self.piper = None
    
    def initialize_camera(self):
        """카메라 초기화"""
        print("\n📷 RealSense 카메라 초기화...")
        self.pipeline = rs.pipeline()
        self.config = rs.config()
        self.config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
        self.config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
        
        try:
            self.profile = self.pipeline.start(self.config)
            depth_sensor = self.profile.get_device().first_depth_sensor()
            self.depth_scale = depth_sensor.get_depth_scale()
            self.align = rs.align(rs.stream.color)
            print("✅ RealSense 준비 완료")
        except Exception as e:
            print(f"❌ RealSense 오류: {e}")
            sys.exit(1)
    
    def initialize_mediapipe(self):
        """MediaPipe 초기화"""
        print("🖐️  MediaPipe Hands 초기화...")
        self.mp_hands = mp.solutions.hands
        self.mp_draw = mp.solutions.drawing_utils
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7
        )
        print("✅ MediaPipe 준비 완료")
    
    def move_to_home_position(self):
        """홈 포지션으로 이동"""
        if not self.piper:
            return
        
        self.control_enabled = False
        time.sleep(0.2)

        try:
            # MOVE J 모드로 변경
            self.piper.ModeCtrl(
                ctrl_mode=0x01,
                move_mode=0x01,      # MOVE J
                move_spd_rate_ctrl=20,
                is_mit_mode=0x00
            )
            time.sleep(0.2)
            
            # 홈 포지션 (안전한 자세)
            self.piper.JointCtrl(
                joint_1=0,
                joint_2=0,
                joint_3=0,
                joint_4=0,
                joint_5=0,
                joint_6=0
            )
            time.sleep(2.0)
            
            # MOVE P 모드로 복귀
            self.piper.ModeCtrl(
                ctrl_mode=0x01,
                move_mode=0x00,      # MOVE P
                move_spd_rate_ctrl=20,
                is_mit_mode=0x00
            )
            time.sleep(0.2)
            
        except Exception as e:
            print(f"⚠️  홈 포지션 이동 실패: {e}")
    
    def get_hand_3d_position(self, hand_landmarks, depth_frame, intrinsics):
        """손목의 3D 위치"""
        wrist = hand_landmarks.landmark[self.mp_hands.HandLandmark.WRIST]
        h, w = depth_frame.shape
        x_pixel = int(np.clip(wrist.x * w, 0, w - 1))
        y_pixel = int(np.clip(wrist.y * h, 0, h - 1))
        
        depth = depth_frame[y_pixel, x_pixel] * self.depth_scale
        if depth == 0:
            region = depth_frame[max(0, y_pixel-5):min(h, y_pixel+5),
                                max(0, x_pixel-5):min(w, x_pixel+5)]
            depth = np.mean(region[region > 0]) * self.depth_scale if np.any(region > 0) else 0
        
        if depth > 0:
            point_3d = rs.rs2_deproject_pixel_to_point(intrinsics, [x_pixel, y_pixel], depth)
            return np.array(point_3d)
        return None
    
    def calculate_hand_orientation(self, hand_landmarks, depth_frame, intrinsics):
        """손의 자세 계산"""
        try:
            wrist = hand_landmarks.landmark[self.mp_hands.HandLandmark.WRIST]
            middle_mcp = hand_landmarks.landmark[self.mp_hands.HandLandmark.MIDDLE_FINGER_MCP]
            index_mcp = hand_landmarks.landmark[self.mp_hands.HandLandmark.INDEX_FINGER_MCP]
            
            h, w = depth_frame.shape
            
            def get_3d_point(landmark):
                x_pixel = int(np.clip(landmark.x * w, 0, w - 1))
                y_pixel = int(np.clip(landmark.y * h, 0, h - 1))
                depth = depth_frame[y_pixel, x_pixel] * self.depth_scale
                if depth == 0:
                    region = depth_frame[max(0, y_pixel-5):min(h, y_pixel+5),
                                        max(0, x_pixel-5):min(w, x_pixel+5)]
                    depth = np.mean(region[region > 0]) * self.depth_scale if np.any(region > 0) else 0
                if depth > 0:
                    return np.array(rs.rs2_deproject_pixel_to_point(intrinsics, [x_pixel, y_pixel], depth))
                return None
            
            wrist_3d = get_3d_point(wrist)
            middle_3d = get_3d_point(middle_mcp)
            index_3d = get_3d_point(index_mcp)
            
            if wrist_3d is None or middle_3d is None or index_3d is None:
                return None
            
            # 손 방향 벡터
            hand_forward = middle_3d - wrist_3d
            hand_right = index_3d - middle_3d
            
            hand_forward = hand_forward / (np.linalg.norm(hand_forward) + 1e-6)
            hand_right = hand_right / (np.linalg.norm(hand_right) + 1e-6)
            
            # Roll, Pitch, Yaw 계산
            pitch = math.atan2(-hand_forward[1], math.sqrt(hand_forward[0]**2 + hand_forward[2]**2))
            yaw = math.atan2(hand_forward[0], hand_forward[2])
            roll = math.atan2(hand_right[1], hand_right[0])
            
            return np.array([roll, pitch, yaw])
            
        except Exception as e:
            return None
    
    def calculate_finger_distance(self, hand_landmarks):
        """엄지와 검지 사이의 거리 계산"""
        try:
            thumb_tip = hand_landmarks.landmark[self.mp_hands.HandLandmark.THUMB_TIP]
            index_tip = hand_landmarks.landmark[self.mp_hands.HandLandmark.INDEX_FINGER_TIP]
            
            dx = thumb_tip.x - index_tip.x
            dy = thumb_tip.y - index_tip.y
            distance = math.sqrt(dx**2 + dy**2)
            
            return distance
        except:
            return None
    
    def calibrate(self, hand_pos, hand_orient):
        """캘리브레이션"""
        self.hand_home_pos = hand_pos.copy()
        self.hand_home_orient = hand_orient.copy()
        self.is_calibrated = True
        print(f"✅ 캘리브레이션 완료!")
        print(f"   손 홈 위치: X={hand_pos[0]:.3f}, Y={hand_pos[1]:.3f}, Z={hand_pos[2]:.3f}")
    
    def hand_to_robot_pose(self, hand_pos, hand_orient):
        """손 포즈를 로봇 포즈로 변환 (좌측 카메라 뷰 최적화)"""
        if not self.is_calibrated or self.hand_home_pos is None:
            return None, None
        
        # 손 이동량
        hand_delta = hand_pos - self.hand_home_pos
        orient_delta = hand_orient - self.hand_home_orient
        
        # 좌표 변환: 좌측 카메라 (Depth 정보 활용)
        # 카메라 X (좌우) → 로봇 X (전후)
        #   왼쪽(-X) → 앞으로(+X)
        #   오른쪽(+X) → 뒤로(-X)
        # 카메라 Y (상하) → 로봇 Z (상하)
        #   위(+Y) → 위(+Z)
        #   아래(-Y) → 아래(-Z)
        # 카메라 Z (Depth, 전후) → 로봇 Y (좌우) + Yaw 회전
        #   가까이(-Z) → 왼쪽(-Y) + 왼쪽 회전(-Yaw)
        #   멀리(+Z) → 오른쪽(+Y) + 오른쪽 회전(+Yaw)
        
        robot_delta = np.array([
            -hand_delta[0],  # 카메라 X (좌우) → 로봇 X (전후, 반전)
            hand_delta[2],   # 카메라 Z (Depth) → 로봇 Y (좌우)
            hand_delta[1]    # 카메라 Y (상하) → 로봇 Z (상하)
        ])
        
        # 로봇 목표 위치
        target_pos = self.robot_home_pos + robot_delta * self.pos_scale
        target_pos = np.clip(target_pos, 
                           [self.workspace['x_min'], self.workspace['y_min'], self.workspace['z_min']],
                           [self.workspace['x_max'], self.workspace['y_max'], self.workspace['z_max']])
        
        # 🛡️ Z축 안전 하한선 적용 (홈 포지션 아래로 안 내려감)
        target_pos[2] = max(target_pos[2], self.home_z_limit)
        
        # 자세 변환: Depth 이동 → Yaw 회전
        # 가까이(-Z) → 왼쪽 회전(-Yaw)
        # 멀리(+Z) → 오른쪽 회전(+Yaw)
        yaw_from_depth = hand_delta[2] * 2.0  # Depth를 Yaw로 매핑 (감도 2배)
        
        # 로봇 목표 자세
        target_orient = np.array(self.robot_home_orient).copy()
        target_orient[0] += orient_delta[0] * self.orient_scale  # Roll
        target_orient[1] += orient_delta[1] * self.orient_scale  # Pitch
        target_orient[2] += yaw_from_depth                        # Yaw (Depth→회전)
        
        # 스무딩
        target_pos = np.array(self.prev_position) * (1 - self.pos_smooth) + np.array(target_pos) * self.pos_smooth
        target_orient = np.array(self.prev_orientation) * (1 - self.orient_smooth) + np.array(target_orient) * self.orient_smooth
        
        # 저장
        self.prev_position = np.array(target_pos)
        self.prev_orientation = np.array(target_orient)
        
        return target_pos, target_orient
    
    def send_robot_command(self, position, orientation, finger_distance=None):
        """로봇에 명령 전송"""
        if not self.piper:
            return
        
        current_time = time.time()
        if current_time - self.last_command_time < self.command_interval:
            return
        
        try:
            # 위치 변환 (m → μm)
            X = int(round(position[0] * 1000 * 1000))
            Y = int(round(position[1] * 1000 * 1000))
            Z = int(round(position[2] * 1000 * 1000))
            
            # 자세 변환 (rad → mdeg)
            RX = int(round(math.degrees(orientation[0]) * 1000))
            RY = int(round(math.degrees(orientation[1]) * 1000))
            RZ = int(round(math.degrees(orientation[2]) * 1000))
            
            # End pose 명령
            self.piper.EndPoseCtrl(X, Y, Z, RX, RY, RZ)
            
            # 그리퍼 제어 (손가락 간격)
            if finger_distance is not None:
                gripper_angle = int(np.interp(finger_distance, [0.0, 0.3], [10000, 80000]))
                gripper_angle = np.clip(gripper_angle, 10000, 80000)
                
                self.piper.GripperCtrl(
                    gripper_angle=gripper_angle,
                    gripper_effort=1000,
                    gripper_code=0x01,
                    set_zero=0x00
                )
            
            self.last_command_time = current_time
            
        except Exception as e:
            print(f"❌ 명령 전송 실패: {e}")
    
    def safe_shutdown(self):
        """안전한 종료 시퀀스"""
        if self.shutdown_in_progress or not self.piper:
            return
        
        self.shutdown_in_progress = True
        print("\n🛡️  안전 종료 시퀀스 시작...")
        
        try:
            # 1. 제어 중지
            self.control_enabled = False
            time.sleep(0.2)
            
            # 2. 그리퍼 열기
            print("🖐️  그리퍼 열기...")
            self.piper.GripperCtrl(
                gripper_angle=80000,
                gripper_effort=500,
                gripper_code=0x01,
                set_zero=0x00
            )
            time.sleep(0.5)
            
            # 3. 홈 포지션으로 이동 (필수!)
            print("🏠 홈 포지션으로 복귀 중...")
            self.piper.ModeCtrl(
                ctrl_mode=0x01,
                move_mode=0x01,      # MOVE J (안전)
                move_spd_rate_ctrl=20,
                is_mit_mode=0x00
            )
            time.sleep(0.5)
            
            # 관절 제어로 홈 포지션
            self.piper.JointCtrl(
                joint_1=0,
                joint_2=0,
                joint_3=0,
                joint_4=0,
                joint_5=0,
                joint_6=0
            )
            print("⏳ 이동 완료 대기 중...")
            time.sleep(3.0)  # 충분한 시간 대기
            print("<<<< 이동 완료 >>>>")
            
            # 4. 대기 모드 전환
            print("😴 대기 모드로 전환...")
            self.piper.ModeCtrl(0x00, 0x01, 10, 0x00)
            time.sleep(0.5)
            print("<<<< 대기 모드 전환 완료 >>>>")

            # 5. 리셋으로 토크 해제
            print("🔓 토크 해제 (리셋)...")
            self.piper.ResetPiper()
            time.sleep(0.5)
            
            # 6. 연결 해제
            self.piper.DisconnectPort()
            print("✅ 안전 종료 완료!")
            
        except Exception as e:
            print(f"⚠️  안전 종료 중 오류: {e}")
            # 오류가 발생해도 최소한 홈 포지션 시도
            try:
                self.move_to_home_position()
                # self.piper.ResetPiper()
                time.sleep(0.5)
                self.piper.DisconnectPort()
            except:
                pass
    
    def draw_ui(self, image, hand_pos, robot_pos, finger_dist):
        """UI 그리기"""
        h, w, _ = image.shape
        
        # 배경
        overlay = image.copy()
        cv2.rectangle(overlay, (10, 10), (w-10, 200), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.65, image, 0.35, 0, image)
        
        # 제목
        cv2.putText(image, "PIPER Safe Control v3", (20, 40),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        
        # 연결 상태
        status = "Connected" if self.piper else "Disconnected"
        color = (0, 255, 0) if self.piper else (0, 0, 255)
        cv2.putText(image, f"Robot: {status}", (20, 70),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        # 제어 상태
        if self.control_enabled:
            status_text = "ACTIVE"
            status_color = (0, 255, 0)
        elif self.is_calibrated:
            status_text = "PAUSED (Press SPACE)"
            status_color = (0, 165, 255)
        else:
            status_text = "Press [C] to Calibrate"
            status_color = (0, 0, 255)
        cv2.putText(image, f"Control: {status_text}", (20, 95),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, status_color, 2)
        
        # 안전 표시
        cv2.putText(image, f"Z-Limit: {self.home_z_limit:.3f}m", (20, 120),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
        
        # 손 정보
        y_offset = 145
        if hand_pos is not None:
            cv2.putText(image, f"Hand: X={hand_pos[0]:.2f} Y={hand_pos[1]:.2f} Z={hand_pos[2]:.2f}",
                       (20, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
            y_offset += 25
        
        if finger_dist is not None:
            cv2.putText(image, f"Finger: {finger_dist:.3f}", (20, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 200, 0), 1)
        
        # 조작 가이드
        cv2.putText(image, "[C]alibrate [SPACE]On/Off [H]ome [Q]uit", (10, h-20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
    
    def run(self):
        """메인 루프"""
        try:
            color_profile = self.profile.get_stream(rs.stream.color)
            intrinsics = color_profile.as_video_stream_profile().get_intrinsics()
            
            print("▶️  프로그램 시작! 손을 카메라 앞에 위치시키세요.")
            print("🛡️  Ctrl+C를 눌러도 안전하게 종료됩니다.\n")
            
            while self.is_running:
                # 비상 종료 체크
                if self.emergency_shutdown:
                    break
                
                frames = self.pipeline.wait_for_frames()
                aligned = self.align.process(frames)
                depth_frame = aligned.get_depth_frame()
                color_frame = aligned.get_color_frame()
                
                if not depth_frame or not color_frame:
                    continue
                
                depth_image = np.asanyarray(depth_frame.get_data())
                color_image = np.asanyarray(color_frame.get_data())
                rgb_image = cv2.cvtColor(color_image, cv2.COLOR_BGR2RGB)
                
                # 손 검출
                results = self.hands.process(rgb_image)
                
                hand_pos = None
                robot_pos = None
                finger_dist = None
                
                if results.multi_hand_landmarks:
                    for hand_landmarks in results.multi_hand_landmarks:
                        # 랜드마크 그리기
                        self.mp_draw.draw_landmarks(
                            color_image, hand_landmarks, self.mp_hands.HAND_CONNECTIONS,
                            self.mp_draw.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=3),
                            self.mp_draw.DrawingSpec(color=(255, 0, 0), thickness=2)
                        )
                        
                        # 손 위치와 자세
                        hand_pos = self.get_hand_3d_position(hand_landmarks, depth_image, intrinsics)
                        hand_orient = self.calculate_hand_orientation(hand_landmarks, depth_image, intrinsics)
                        finger_dist = self.calculate_finger_distance(hand_landmarks)
                        
                        # 로봇 제어
                        if hand_pos is not None and hand_orient is not None:
                            robot_pos, robot_orient = self.hand_to_robot_pose(hand_pos, hand_orient)
                            
                            if self.control_enabled and robot_pos is not None:
                                self.send_robot_command(robot_pos, robot_orient, finger_dist)
                
                # UI
                self.draw_ui(color_image, hand_pos, robot_pos, finger_dist)
                
                # 화면 출력
                cv2.imshow('PIPER Safe Control v3', color_image)
                
                # 키보드
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    print("\n👋 정상 종료 요청...")
                    self.is_running = False
                elif key == ord('c') and hand_pos is not None and hand_orient is not None:
                    self.calibrate(hand_pos, hand_orient)
                elif key == ord(' '):
                    if self.is_calibrated:
                        self.control_enabled = not self.control_enabled
                        print(f"🎮 제어: {'활성화 ✅' if self.control_enabled else '일시정지 ⏸️'}")
                elif key == ord('h'):
                    print("🏠 홈 포지션으로 이동...")
                    self.control_enabled = False
                    self.move_to_home_position()
        
        except KeyboardInterrupt:
            print("\n⚠️  KeyboardInterrupt 감지")
            self.emergency_shutdown = True
        except Exception as e:
            print(f"\n❌ 오류 발생: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.cleanup()
    
    def cleanup(self):
        """정리"""
        if self.shutdown_in_progress:
            return
        
        print("\n🧹 시스템 종료 중...")
        
        # 안전 종료 시퀀스 실행
        if self.piper:
            self.safe_shutdown()
        
        # 카메라 종료
        try:
            self.pipeline.stop()
        except:
            pass
        
        cv2.destroyAllWindows()
        
        try:
            self.hands.close()
        except:
            pass
        
        print("✅ 종료 완료")


def main():
    """메인 함수"""
    try:
        teleop = SafePiperTeleoperation()
        teleop.run()
    except Exception as e:
        print(f"\n❌ 프로그램 오류: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()