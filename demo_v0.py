#!/usr/bin/env python3
"""
PIPER 로봇 암 손동작+자세 텔레오퍼레이션 시스템 (개선 v2)
- 손의 위치 (X, Y, Z) 추적
- 손의 자세 (Roll, Pitch, Yaw) 추적
- 손가락 간격으로 그리퍼 제어
- 실시간 PIPER 제어
- 재밌는 기능 3가지 추가
Intel RealSense D435I + MediaPipe

주요 개선 사항:
1. float to int 변환 오류 수정
2. 손가락 간격으로 그리퍼 제어 구현
3. 관절 제어 개선
4. 변화 감지하여 출력 최적화
5. 재밌는 기능 3가지 추가:
   - [W] 손 흔들기 감지 → 웨이브 제스처
   - [D] 데모 모드 (자동 동작 시연)
   - [R] 녹화/재생 모드 (동작 녹화 및 재생)
"""

import cv2
import numpy as np
import pyrealsense2 as rs
import mediapipe as mp
import time
import sys
import math
from collections import deque
import json
import os

# PIPER SDK
from piper_sdk import *


class FullHandPoseTeleoperation:
    """손의 위치와 자세를 모두 추적하는 텔레오퍼레이션"""
    
    def __init__(self):
        """초기화"""
        print("\n" + "=" * 70)
        print("   🤖 PIPER 로봇 완전 제어 v2 (향상된 버전)")
        print("   ✋ 손 위치 + 자세 + 그리퍼 제어")
        print("   📷 Intel RealSense D435I")
        print("   🎮 새로운 기능: 웨이브, 데모, 녹화/재생")
        print("=" * 70 + "\n")
        
        # PIPER 로봇 초기화
        self.piper = None
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
            print("🔧 로봇 암 활성화 중...")
            self.piper.EnableArm(7)  # 모든 관절 활성화
            time.sleep(1.0)
            
            # 활성화 상태 확인
            enable_status = self.piper.GetArmEnableStatus()
            if all(enable_status):
                print("✅ 로봇 암 활성화 완료")
            else:
                print(f"⚠️  일부 관절 미활성화: {enable_status}")
            
            # 4단계: 제어 모드 설정
            print("🔧 제어 모드 설정 중...")
            self.piper.ModeCtrl(
                ctrl_mode=0x01,      # CAN 제어
                move_mode=0x00,      # MOVE P (Cartesian 제어로 변경)
                move_spd_rate_ctrl=50,
                is_mit_mode=0x00
            )
            time.sleep(0.3)
            print("✅ 제어 모드 설정 완료 (CAN + MOVE P)")
            
            # 5단계: 그리퍼 초기화
            print("🔧 그리퍼 초기화 중...")
            self.piper.GripperCtrl(
                gripper_angle=50000,    # 50mm
                gripper_effort=1000,
                gripper_code=0x03,      # 활성화 + 에러 클리어
                set_zero=0x00
            )
            time.sleep(0.5)
            print("✅ 그리퍼 초기화 완료")
            
            # 6단계: 홈 포지션으로 이동
            print("🏠 홈 포지션으로 이동 중...")
            self.move_to_home_position()
            print("✅ 초기화 완료!")
            
        except Exception as e:
            print(f"❌ PIPER 초기화 실패: {e}")
            import traceback
            traceback.print_exc()
            self.piper = None
        
        # RealSense 초기화
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
        
        # MediaPipe Hands
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
        
        # 작업 공간 (미터)
        self.workspace = {
            'x_min': 0.2, 'x_max': 0.5,
            'y_min': -0.3, 'y_max': 0.3,
            'z_min': 0.1, 'z_max': 0.5
        }
        
        # 캘리브레이션
        self.is_calibrated = False
        self.hand_home_pos = None
        self.hand_home_orient = None
        self.robot_home_pos = [0.35, 0.0, 0.3]
        self.robot_home_orient = [0.0, math.pi, 0.0]
        
        # 제어 파라미터
        self.pos_scale = 1.0
        self.orient_scale = 0.5
        self.pos_smooth = 0.3
        self.orient_smooth = 0.4
        
        self.prev_position = np.array(self.robot_home_pos)
        self.prev_orientation = np.array(self.robot_home_orient)
        
        # 상태
        self.is_running = True
        self.gripper_open = True
        self.control_enabled = False
        
        # 성능
        self.last_command_time = 0
        self.command_interval = 0.05  # 20Hz
        
        # 변화 감지용 이전 값 저장
        self.prev_joint_values = None
        self.prev_gripper_value = None
        self.prev_end_pose = None
        self.value_change_threshold = 100  # 0.1도 또는 0.1mm 변화 감지
        
        # 🎮 새 기능 1: 웨이브 제스처 감지
        self.wave_detector = WaveGestureDetector()
        self.wave_mode = False
        
        # 🎮 새 기능 2: 데모 모드
        self.demo_mode = False
        self.demo_step = 0
        
        # 🎮 새 기능 3: 녹화/재생
        self.recording = False
        self.playing = False
        self.recorded_motions = []
        self.recording_file = "piper_motions.json"
        
        print("\n✅ 시스템 준비 완료!")
        print("📌 [C] 캘리브레이션  [G] 그리퍼  [SPACE] 제어 On/Off  [H] 홈")
        print("🎮 [W] 웨이브 모드  [D] 데모  [R] 녹화  [P] 재생  [Q] 종료\n")
    
    def move_to_home_position(self):
        """안전한 홈 포지션으로 이동"""
        if not self.piper:
            return
        
        try:
            # MOVE J 모드로 변경
            self.piper.ModeCtrl(
                ctrl_mode=0x01,
                move_mode=0x01,      # MOVE J
                move_spd_rate_ctrl=30,
                is_mit_mode=0x00
            )
            time.sleep(0.2)
            
            # 홈 포지션 관절 각도 (0.001도 단위)
            self.piper.JointCtrl(
                joint_1=0,
                joint_2=0,
                joint_3=0,
                joint_4=0,
                joint_5=0,
                joint_6=0
            )
            time.sleep(2.0)
            
            # MOVE P 모드로 변경
            self.piper.ModeCtrl(
                ctrl_mode=0x01,
                move_mode=0x00,      # MOVE P
                move_spd_rate_ctrl=50,
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
        """손의 자세 계산 (Roll, Pitch, Yaw)"""
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
        """엄지와 검지 사이의 거리 계산 (그리퍼 제어용)"""
        try:
            thumb_tip = hand_landmarks.landmark[self.mp_hands.HandLandmark.THUMB_TIP]
            index_tip = hand_landmarks.landmark[self.mp_hands.HandLandmark.INDEX_FINGER_TIP]
            
            # 2D 거리 계산
            dx = thumb_tip.x - index_tip.x
            dy = thumb_tip.y - index_tip.y
            distance = math.sqrt(dx**2 + dy**2)
            
            return distance
        except:
            return None
    
    def calibrate(self, hand_pos, hand_orient):
        """현재 손 위치를 로봇 홈으로 설정"""
        self.hand_home_pos = hand_pos.copy()
        self.hand_home_orient = hand_orient.copy()
        self.is_calibrated = True
        print(f"✅ 캘리브레이션 완료!")
        print(f"   손 홈 위치: X={hand_pos[0]:.3f}, Y={hand_pos[1]:.3f}, Z={hand_pos[2]:.3f}")
        print(f"   손 홈 자세: R={math.degrees(hand_orient[0]):.1f}°, "
              f"P={math.degrees(hand_orient[1]):.1f}°, Y={math.degrees(hand_orient[2]):.1f}°")
    
    def hand_to_robot_pose(self, hand_pos, hand_orient):
        """손 포즈를 로봇 포즈로 변환"""
        if not self.is_calibrated or self.hand_home_pos is None:
            return None, None
        
        # 손 이동량
        hand_delta = hand_pos - self.hand_home_pos
        orient_delta = hand_orient - self.hand_home_orient
        
        # 로봇 목표 위치
        target_pos = self.robot_home_pos + hand_delta * self.pos_scale
        target_pos = np.clip(target_pos, 
                           [self.workspace['x_min'], self.workspace['y_min'], self.workspace['z_min']],
                           [self.workspace['x_max'], self.workspace['y_max'], self.workspace['z_max']])
        
        # 로봇 목표 자세
        target_orient = self.robot_home_orient + orient_delta * self.orient_scale
        
        # 스무딩
        target_pos = self.prev_position * (1 - self.pos_smooth) + target_pos * self.pos_smooth
        target_orient = self.prev_orientation * (1 - self.orient_smooth) + target_orient * self.orient_smooth
        
        self.prev_position = target_pos
        self.prev_orientation = target_orient
        
        return target_pos, target_orient
    
    def send_robot_command(self, position, orientation, finger_distance=None):
        """로봇에 명령 전송"""
        if not self.piper:
            return
        
        current_time = time.time()
        if current_time - self.last_command_time < self.command_interval:
            return
        
        try:
            # 위치를 마이크로미터로 변환 (m → μm)
            X = int(round(position[0] * 1000 * 1000))  # m → mm → μm
            Y = int(round(position[1] * 1000 * 1000))
            Z = int(round(position[2] * 1000 * 1000))
            
            # 자세를 밀리도로 변환 (rad → deg → mdeg)
            RX = int(round(math.degrees(orientation[0]) * 1000))
            RY = int(round(math.degrees(orientation[1]) * 1000))
            RZ = int(round(math.degrees(orientation[2]) * 1000))
            
            # End pose 명령 전송
            self.piper.EndPoseCtrl(X, Y, Z, RX, RY, RZ)
            
            # 그리퍼 제어 (손가락 간격 기반)
            if finger_distance is not None:
                # 손가락 거리를 그리퍼 각도로 매핑 (0.0-0.3 → 10000-80000 μm)
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
    
    def toggle_gripper(self):
        """그리퍼 토글"""
        if not self.piper:
            return
        
        try:
            if self.gripper_open:
                # 닫기
                self.piper.GripperCtrl(
                    gripper_angle=20000,  # 20mm
                    gripper_effort=1000,
                    gripper_code=0x01,
                    set_zero=0x00
                )
                self.gripper_open = False
                print("🔴 그리퍼 닫힘")
            else:
                # 열기
                self.piper.GripperCtrl(
                    gripper_angle=80000,  # 80mm
                    gripper_effort=1000,
                    gripper_code=0x01,
                    set_zero=0x00
                )
                self.gripper_open = True
                print("🟢 그리퍼 열림")
        except Exception as e:
            print(f"❌ 그리퍼 제어 실패: {e}")
    
    def print_if_changed(self):
        """값이 변경되었을 때만 출력"""
        if not self.piper:
            return
        
        try:
            # 관절 정보 가져오기
            joint_msg = self.piper.GetArmJointMsgs()
            current_joints = [
                joint_msg.joint_state.joint_1,
                joint_msg.joint_state.joint_2,
                joint_msg.joint_state.joint_3,
                joint_msg.joint_state.joint_4,
                joint_msg.joint_state.joint_5,
                joint_msg.joint_state.joint_6
            ]
            
            # 그리퍼 정보
            gripper_msg = self.piper.GetArmGripperMsgs()
            current_gripper = gripper_msg.gripper_state.grippers_angle
            
            # 엔드포즈 정보
            end_pose = self.piper.GetArmEndPoseMsgs()
            current_end_pose = [
                end_pose.end_pose.X_axis,
                end_pose.end_pose.Y_axis,
                end_pose.end_pose.Z_axis
            ]
            
            # 변화 감지
            joints_changed = False
            gripper_changed = False
            pose_changed = False
            
            if self.prev_joint_values is not None:
                for i, (curr, prev) in enumerate(zip(current_joints, self.prev_joint_values)):
                    if abs(curr - prev) > self.value_change_threshold:
                        joints_changed = True
                        break
            else:
                joints_changed = True
            
            if self.prev_gripper_value is not None:
                if abs(current_gripper - self.prev_gripper_value) > self.value_change_threshold:
                    gripper_changed = True
            else:
                gripper_changed = True
            
            if self.prev_end_pose is not None:
                for curr, prev in zip(current_end_pose, self.prev_end_pose):
                    if abs(curr - prev) > self.value_change_threshold * 10:  # 위치는 더 큰 변화
                        pose_changed = True
                        break
            else:
                pose_changed = True
            
            # 변화가 있을 때만 출력
            if joints_changed or gripper_changed or pose_changed:
                print("\n" + "="*60)
                if joints_changed:
                    print(f"🔧 관절: J1={current_joints[0]/1000:.1f}° "
                          f"J2={current_joints[1]/1000:.1f}° "
                          f"J3={current_joints[2]/1000:.1f}° "
                          f"J4={current_joints[3]/1000:.1f}° "
                          f"J5={current_joints[4]/1000:.1f}° "
                          f"J6={current_joints[5]/1000:.1f}°")
                
                if gripper_changed:
                    print(f"✋ 그리퍼: {current_gripper/1000:.1f}mm")
                
                if pose_changed:
                    print(f"📍 위치: X={current_end_pose[0]/1000:.1f}mm "
                          f"Y={current_end_pose[1]/1000:.1f}mm "
                          f"Z={current_end_pose[2]/1000:.1f}mm")
                print("="*60)
            
            # 현재 값 저장
            self.prev_joint_values = current_joints
            self.prev_gripper_value = current_gripper
            self.prev_end_pose = current_end_pose
            
        except Exception as e:
            pass
    
    # 🎮 새 기능 1: 웨이브 제스처
    def check_wave_gesture(self, hand_landmarks):
        """손 흔들기 제스처 감지"""
        return self.wave_detector.detect(hand_landmarks)
    
    def perform_wave_motion(self):
        """웨이브 동작 수행"""
        if not self.piper:
            return
        
        print("👋 웨이브 동작 수행!")
        try:
            # 좌우로 흔들기
            for _ in range(3):
                self.piper.JointCtrl(0, 0, 0, 0, 0, 30000)  # J6 30도
                time.sleep(0.5)
                self.piper.JointCtrl(0, 0, 0, 0, 0, -30000)  # J6 -30도
                time.sleep(0.5)
            self.piper.JointCtrl(0, 0, 0, 0, 0, 0)  # 원위치
        except Exception as e:
            print(f"❌ 웨이브 실패: {e}")
    
    # 🎮 새 기능 2: 데모 모드
    def run_demo_sequence(self):
        """자동 데모 동작"""
        if not self.piper:
            return
        
        print(f"🎬 데모 단계 {self.demo_step + 1}/4")
        
        try:
            if self.demo_step == 0:
                # 1단계: 위로 이동
                print("  ⬆️  위로 이동")
                self.piper.EndPoseCtrl(350000, 0, 400000, 0, 180000, 0)
            elif self.demo_step == 1:
                # 2단계: 그리퍼 닫기
                print("  ✊ 그리퍼 닫기")
                self.piper.GripperCtrl(20000, 1000, 0x01, 0x00)
            elif self.demo_step == 2:
                # 3단계: 아래로 이동
                print("  ⬇️  아래로 이동")
                self.piper.EndPoseCtrl(350000, 0, 200000, 0, 180000, 0)
            elif self.demo_step == 3:
                # 4단계: 그리퍼 열기
                print("  🖐️  그리퍼 열기")
                self.piper.GripperCtrl(80000, 1000, 0x01, 0x00)
            
            self.demo_step = (self.demo_step + 1) % 4
            time.sleep(2.0)
            
        except Exception as e:
            print(f"❌ 데모 실패: {e}")
    
    # 🎮 새 기능 3: 녹화/재생
    def start_recording(self):
        """동작 녹화 시작"""
        self.recording = True
        self.recorded_motions = []
        print("🔴 녹화 시작!")
    
    def stop_recording(self):
        """녹화 중지 및 저장"""
        self.recording = False
        if self.recorded_motions:
            with open(self.recording_file, 'w') as f:
                json.dump(self.recorded_motions, f)
            print(f"💾 {len(self.recorded_motions)}개 프레임 저장됨: {self.recording_file}")
        else:
            print("⚠️  녹화된 데이터 없음")
    
    def record_current_state(self):
        """현재 상태 기록"""
        if not self.recording or not self.piper:
            return
        
        try:
            joint_msg = self.piper.GetArmJointMsgs()
            gripper_msg = self.piper.GetArmGripperMsgs()
            
            state = {
                'joints': [
                    joint_msg.joint_state.joint_1,
                    joint_msg.joint_state.joint_2,
                    joint_msg.joint_state.joint_3,
                    joint_msg.joint_state.joint_4,
                    joint_msg.joint_state.joint_5,
                    joint_msg.joint_state.joint_6
                ],
                'gripper': gripper_msg.gripper_state.grippers_angle
            }
            self.recorded_motions.append(state)
        except:
            pass
    
    def play_recording(self):
        """녹화된 동작 재생"""
        if not os.path.exists(self.recording_file):
            print("❌ 녹화 파일 없음")
            return
        
        try:
            with open(self.recording_file, 'r') as f:
                motions = json.load(f)
            
            print(f"▶️  {len(motions)}개 프레임 재생 중...")
            self.playing = True
            
            for i, motion in enumerate(motions):
                if not self.playing:
                    break
                
                self.piper.JointCtrl(*motion['joints'])
                self.piper.GripperCtrl(motion['gripper'], 1000, 0x01, 0x00)
                time.sleep(0.1)
                
                if i % 10 == 0:
                    print(f"  재생 중... {i}/{len(motions)}")
            
            self.playing = False
            print("✅ 재생 완료!")
            
        except Exception as e:
            print(f"❌ 재생 실패: {e}")
            self.playing = False
    
    def draw_ui(self, image, hand_pos, hand_orient, robot_pos, robot_orient, finger_dist):
        """UI 그리기"""
        h, w, _ = image.shape
        
        # 배경
        overlay = image.copy()
        cv2.rectangle(overlay, (10, 10), (w-10, 300), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.65, image, 0.35, 0, image)
        
        # 제목
        cv2.putText(image, "Hand Poses-PIPER Teleoperation", (20, 40),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
        
        # 연결 상태
        connection_status = "Connected" if self.piper else "Disconnected"
        connection_color = (0, 255, 0) if self.piper else (0, 0, 255)
        cv2.putText(image, f"Robot: {connection_status}", (20, 70),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, connection_color, 2)
        
        # 제어 상태
        if self.control_enabled:
            status = "ACTIVE"
            color = (0, 255, 0)
        elif self.is_calibrated:
            status = "PAUSED (Press SPACE)"
            color = (0, 165, 255)
        else:
            status = "Press [C] to Calibrate"
            color = (0, 0, 255)
        cv2.putText(image, f"Control: {status}", (20, 95),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        # 특수 모드 표시
        y_offset = 120
        if self.wave_mode:
            cv2.putText(image, "WAVE MODE ON", (20, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)
            y_offset += 25
        if self.demo_mode:
            cv2.putText(image, f"DEMO MODE (Step {self.demo_step+1}/4)", (20, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 2)
            y_offset += 25
        if self.recording:
            cv2.putText(image, f"RECORDING ({len(self.recorded_motions)} frames)", (20, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
            y_offset += 25
        if self.playing:
            cv2.putText(image, "PLAYING...", (20, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            y_offset += 25
        
        # 손 정보
        y_offset += 10
        if hand_pos is not None:
            cv2.putText(image, "Hand Position:", (20, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            cv2.putText(image, f"  X={hand_pos[0]:.3f} Y={hand_pos[1]:.3f} Z={hand_pos[2]:.3f}m",
                       (20, y_offset+20), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
            y_offset += 45
        
        if finger_dist is not None:
            cv2.putText(image, f"Finger Dist: {finger_dist:.3f}", (20, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 200, 0), 1)
            y_offset += 25
        
        # 조작 가이드
        cv2.putText(image, "[C]al [SPC]On/Off [G]rip [H]ome", (10, h-50),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
        cv2.putText(image, "[W]ave [D]emo [R]ec [P]lay [Q]uit", (10, h-25),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 0), 1)
    
    def run(self):
        """메인 루프"""
        try:
            color_profile = self.profile.get_stream(rs.stream.color)
            intrinsics = color_profile.as_video_stream_profile().get_intrinsics()
            
            print("▶️  프로그램 시작! 손을 카메라 앞에 위치시키세요.\n")
            
            frame_count = 0
            last_print_time = 0
            
            while self.is_running:
                frames = self.pipeline.wait_for_frames()
                aligned = self.align.process(frames)
                depth_frame = aligned.get_depth_frame()
                color_frame = aligned.get_color_frame()
                
                if not depth_frame or not color_frame:
                    continue
                
                depth_image = np.asanyarray(depth_frame.get_data())
                color_image = np.asanyarray(color_frame.get_data())
                rgb_image = cv2.cvtColor(color_image, cv2.COLOR_BGR2RGB)
                
                # 변화 감지 출력 (1초마다)
                if time.time() - last_print_time > 1.0:
                    self.print_if_changed()
                    last_print_time = time.time()
                
                # 데모 모드 실행
                if self.demo_mode and frame_count % 60 == 0:  # 2초마다
                    self.run_demo_sequence()
                
                frame_count += 1
                
                # 손 검출
                results = self.hands.process(rgb_image)
                
                hand_pos = None
                hand_orient = None
                robot_pos = None
                robot_orient = None
                finger_dist = None
                
                if results.multi_hand_landmarks:
                    for hand_landmarks in results.multi_hand_landmarks:
                        # 랜드마크 그리기
                        self.mp_draw.draw_landmarks(
                            color_image, hand_landmarks, self.mp_hands.HAND_CONNECTIONS,
                            self.mp_draw.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=3),
                            self.mp_draw.DrawingSpec(color=(255, 0, 0), thickness=2)
                        )
                        
                        # 손 위치와 자세 계산
                        hand_pos = self.get_hand_3d_position(hand_landmarks, depth_image, intrinsics)
                        hand_orient = self.calculate_hand_orientation(hand_landmarks, depth_image, intrinsics)
                        finger_dist = self.calculate_finger_distance(hand_landmarks)
                        
                        # 웨이브 제스처 감지
                        if self.wave_mode and self.check_wave_gesture(hand_landmarks):
                            self.perform_wave_motion()
                            self.wave_mode = False
                        
                        # 로봇 포즈 계산
                        if hand_pos is not None and hand_orient is not None:
                            robot_pos, robot_orient = self.hand_to_robot_pose(hand_pos, hand_orient)
                            
                            # 로봇 명령 전송
                            if self.control_enabled and robot_pos is not None:
                                self.send_robot_command(robot_pos, robot_orient, finger_dist)
                                
                                # 녹화 중이면 상태 기록
                                if self.recording and frame_count % 5 == 0:
                                    self.record_current_state()
                
                # UI 그리기
                self.draw_ui(color_image, hand_pos, hand_orient, robot_pos, robot_orient, finger_dist)
                
                # 화면 출력
                cv2.imshow('PIPER Full Control v2', color_image)
                
                # 키보드 입력
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    self.is_running = False
                elif key == ord('c') and hand_pos is not None and hand_orient is not None:
                    self.calibrate(hand_pos, hand_orient)
                elif key == ord(' '):  # 스페이스바
                    if self.is_calibrated:
                        self.control_enabled = not self.control_enabled
                        print(f"🎮 제어: {'활성화 ✅' if self.control_enabled else '일시정지 ⏸️'}")
                elif key == ord('g'):
                    self.toggle_gripper()
                elif key == ord('h'):
                    print("🏠 홈 포지션으로 이동...")
                    self.control_enabled = False
                    self.move_to_home_position()
                # 새 기능 키
                elif key == ord('w'):
                    self.wave_mode = not self.wave_mode
                    print(f"👋 웨이브 모드: {'ON' if self.wave_mode else 'OFF'}")
                elif key == ord('d'):
                    self.demo_mode = not self.demo_mode
                    if self.demo_mode:
                        self.demo_step = 0
                        print("🎬 데모 모드 시작")
                    else:
                        print("🎬 데모 모드 종료")
                elif key == ord('r'):
                    if not self.recording:
                        self.start_recording()
                    else:
                        self.stop_recording()
                elif key == ord('p'):
                    if not self.playing:
                        self.control_enabled = False
                        self.play_recording()
        
        except KeyboardInterrupt:
            print("\n🛑 프로그램 중단")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """정리"""
        print("\n 시스템 종료 중...")
        
        if self.piper:
            try:
                # 제어 중지
                self.control_enabled = False
                self.demo_mode = False
                self.wave_mode = False
                time.sleep(0.2)
                
                # 그리퍼 열기
                self.piper.GripperCtrl(
                    gripper_angle=80000,
                    gripper_effort=1000,
                    gripper_code=0x01,
                    set_zero=0x00
                )
                time.sleep(0.3)
                
                # 대기 모드로 전환
                self.piper.ModeCtrl(0x00, 0x01, 50, 0x00)
                time.sleep(0.5)
                self.piper.ResetPiper()
                
                # 연결 해제
                self.piper.DisconnectPort()
                print("✅ PIPER 연결 해제")
            except Exception as e:
                print(f"⚠️  정리 중 오류: {e}")
        
        self.pipeline.stop()
        cv2.destroyAllWindows()
        self.hands.close()
        print("✅ 종료 완료")


class WaveGestureDetector:
    """손 흔들기 제스처 감지"""
    
    def __init__(self, history_size=10, threshold=0.05):
        self.history = deque(maxlen=history_size)
        self.threshold = threshold
    
    def detect(self, hand_landmarks):
        """손목의 좌우 움직임 감지"""
        wrist = hand_landmarks.landmark[mp.solutions.hands.HandLandmark.WRIST]
        self.history.append(wrist.x)
        
        if len(self.history) < self.history.maxlen:
            return False
        
        # 좌우 움직임 크기 계산
        movement = max(self.history) - min(self.history)
        
        # 방향 전환 횟수
        changes = 0
        for i in range(1, len(self.history)):
            if (self.history[i] - self.history[i-1]) * (self.history[i-1] - self.history[i-2] if i > 1 else 1) < 0:
                changes += 1
        
        # 충분히 큰 움직임 + 여러 번 방향 전환
        return movement > self.threshold and changes >= 3


def main():
    """메인 함수"""
    try:
        teleop = FullHandPoseTeleoperation()
        teleop.run()
    except Exception as e:
        print(f"\n❌ 프로그램 오류: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()